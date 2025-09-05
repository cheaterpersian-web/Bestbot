from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.scheduled_messages import MessageType, MessageStatus, CampaignType
from services.scheduled_message_service import ScheduledMessageService


router = Router(name="scheduled_messages")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class CreateMessageStates(StatesGroup):
    waiting_title = State()
    waiting_content = State()
    waiting_type = State()
    waiting_schedule = State()
    waiting_target = State()
    waiting_media = State()


class CreateCampaignStates(StatesGroup):
    waiting_name = State()
    waiting_type = State()
    waiting_description = State()


# Admin scheduled message features
@router.message(Command("create_message"))
async def create_message_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    await message.answer("عنوان پیام را وارد کنید:")
    await state.set_state(CreateMessageStates.waiting_title)


@router.message(CreateMessageStates.waiting_title)
async def create_message_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("محتوای پیام را وارد کنید:")
    await state.set_state(CreateMessageStates.waiting_content)


@router.message(CreateMessageStates.waiting_content)
async def create_message_content(message: Message, state: FSMContext):
    await state.update_data(content=message.text.strip())
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 متن", callback_data="msg_type:text")],
        [InlineKeyboardButton(text="🖼️ تصویر", callback_data="msg_type:image")],
        [InlineKeyboardButton(text="🎥 ویدیو", callback_data="msg_type:video")],
        [InlineKeyboardButton(text="📄 سند", callback_data="msg_type:document")]
    ])
    
    await message.answer("نوع پیام را انتخاب کنید:", reply_markup=kb)
    await state.set_state(CreateMessageStates.waiting_type)


@router.callback_query(F.data.startswith("msg_type:"))
async def create_message_type(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != CreateMessageStates.waiting_type:
        return
    
    msg_type = callback.data.split(":")[1]
    await state.update_data(message_type=msg_type)
    
    if msg_type in ["image", "video", "document"]:
        await callback.message.edit_text("فایل مدیا را ارسال کنید:")
        await state.set_state(CreateMessageStates.waiting_media)
    else:
        await callback.message.edit_text("زمان ارسال را وارد کنید (YYYY-MM-DD HH:MM):")
        await state.set_state(CreateMessageStates.waiting_schedule)
    
    await callback.answer()


@router.message(CreateMessageStates.waiting_media)
async def create_message_media(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_type = data["message_type"]
    
    media_file_id = None
    
    if msg_type == "image" and message.photo:
        media_file_id = message.photo[-1].file_id
    elif msg_type == "video" and message.video:
        media_file_id = message.video.file_id
    elif msg_type == "document" and message.document:
        media_file_id = message.document.file_id
    else:
        await message.answer("لطفاً فایل مناسب ارسال کنید.")
        return
    
    await state.update_data(media_file_id=media_file_id)
    await message.answer("زمان ارسال را وارد کنید (YYYY-MM-DD HH:MM):")
    await state.set_state(CreateMessageStates.waiting_schedule)


@router.message(CreateMessageStates.waiting_schedule)
async def create_message_schedule(message: Message, state: FSMContext):
    try:
        scheduled_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD HH:MM استفاده کنید.")
        return
    
    await state.update_data(scheduled_at=scheduled_at)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 همه کاربران", callback_data="target:all")],
        [InlineKeyboardButton(text="🎯 کاربران جدید", callback_data="target:new_users")],
        [InlineKeyboardButton(text="⭐ کاربران فعال", callback_data="target:active_users")],
        [InlineKeyboardButton(text="💎 کاربران VIP", callback_data="target:vip_users")],
        [InlineKeyboardButton(text="⚠️ کاربران ترک کرده", callback_data="target:churned_users")]
    ])
    
    await message.answer("گروه هدف را انتخاب کنید:", reply_markup=kb)
    await state.set_state(CreateMessageStates.waiting_target)


@router.callback_query(F.data.startswith("target:"))
async def create_message_target(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != CreateMessageStates.waiting_target:
        return
    
    target = callback.data.split(":")[1]
    data = await state.get_data()
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
            )).scalar_one()
            
            # Create scheduled message
            scheduled_message = await ScheduledMessageService.create_scheduled_message(
                session=session,
                title=data["title"],
                content=data["content"],
                scheduled_at=data["scheduled_at"],
                message_type=MessageType(data["message_type"]),
                target_type="all" if target == "all" else "segment",
                target_segments=[target] if target != "all" else None,
                created_by=admin_user.id,
                media_file_id=data.get("media_file_id")
            )
        
        await state.clear()
        
        target_names = {
            "all": "همه کاربران",
            "new_users": "کاربران جدید",
            "active_users": "کاربران فعال",
            "vip_users": "کاربران VIP",
            "churned_users": "کاربران ترک کرده"
        }
        
        await callback.message.edit_text(f"✅ پیام زمان‌بندی شده ایجاد شد!\n\n"
                                       f"عنوان: {data['title']}\n"
                                       f"زمان ارسال: {data['scheduled_at'].strftime('%Y/%m/%d %H:%M')}\n"
                                       f"گروه هدف: {target_names.get(target, target)}\n"
                                       f"تعداد گیرندگان: {scheduled_message.total_recipients}")
        
    except Exception as e:
        await state.clear()
        await callback.message.edit_text(f"❌ خطا در ایجاد پیام: {str(e)}")
    
    await callback.answer()


@router.message(Command("list_messages"))
async def list_messages(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, desc
        from models.scheduled_messages import ScheduledMessage
        
        messages = (await session.execute(
            select(ScheduledMessage)
            .order_by(desc(ScheduledMessage.created_at))
            .limit(10)
        )).scalars().all()
    
    if not messages:
        await message.answer("هیچ پیام زمان‌بندی شده‌ای یافت نشد.")
        return
    
    messages_text = "📋 پیام‌های زمان‌بندی شده:\n\n"
    
    status_emojis = {
        MessageStatus.DRAFT: "📝",
        MessageStatus.SCHEDULED: "⏰",
        MessageStatus.SENDING: "📤",
        MessageStatus.SENT: "✅",
        MessageStatus.FAILED: "❌",
        MessageStatus.CANCELLED: "🚫"
    }
    
    type_emojis = {
        MessageType.TEXT: "📝",
        MessageType.IMAGE: "🖼️",
        MessageType.VIDEO: "🎥",
        MessageType.DOCUMENT: "📄",
        MessageType.AUDIO: "🎵",
        MessageType.VOICE: "🎤",
        MessageType.STICKER: "😀",
        MessageType.ANIMATION: "🎬",
        MessageType.POLL: "📊",
        MessageType.FORWARD: "↗️"
    }
    
    for i, msg in enumerate(messages, 1):
        status_emoji = status_emojis.get(msg.status, "❓")
        type_emoji = type_emojis.get(msg.message_type, "❓")
        date_str = msg.scheduled_at.strftime('%m/%d %H:%M')
        
        messages_text += f"{i}. {status_emoji} {type_emoji} {msg.title}\n"
        messages_text += f"   زمان: {date_str}\n"
        messages_text += f"   گیرندگان: {msg.total_recipients}\n"
        messages_text += f"   ارسال شده: {msg.sent_count}\n\n"
    
    await message.answer(messages_text)


@router.message(Command("create_campaign"))
async def create_campaign_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    await message.answer("نام کمپین را وارد کنید:")
    await state.set_state(CreateCampaignStates.waiting_name)


@router.message(CreateCampaignStates.waiting_name)
async def create_campaign_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 همگانی", callback_data="campaign_type:broadcast")],
        [InlineKeyboardButton(text="🎯 هدفمند", callback_data="campaign_type:targeted")],
        [InlineKeyboardButton(text="📞 پیگیری", callback_data="campaign_type:follow_up")],
        [InlineKeyboardButton(text="🎁 تبلیغاتی", callback_data="campaign_type:promotional")],
        [InlineKeyboardButton(text="📚 آموزشی", callback_data="campaign_type:educational")],
        [InlineKeyboardButton(text="⏰ یادآوری", callback_data="campaign_type:reminder")]
    ])
    
    await message.answer("نوع کمپین را انتخاب کنید:", reply_markup=kb)
    await state.set_state(CreateCampaignStates.waiting_type)


@router.callback_query(F.data.startswith("campaign_type:"))
async def create_campaign_type(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != CreateCampaignStates.waiting_type:
        return
    
    campaign_type = callback.data.split(":")[1]
    await state.update_data(campaign_type=campaign_type)
    
    await callback.message.edit_text("توضیحات کمپین را وارد کنید (اختیاری):")
    await state.set_state(CreateCampaignStates.waiting_description)


@router.message(CreateCampaignStates.waiting_description)
async def create_campaign_description(message: Message, state: FSMContext):
    description = message.text.strip() if message.text.strip() else None
    data = await state.get_data()
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            campaign = await ScheduledMessageService.create_campaign(
                session=session,
                name=data["name"],
                campaign_type=CampaignType(data["campaign_type"]),
                description=description,
                created_by=admin_user.id
            )
        
        await state.clear()
        
        type_names = {
            "broadcast": "همگانی",
            "targeted": "هدفمند",
            "follow_up": "پیگیری",
            "promotional": "تبلیغاتی",
            "educational": "آموزشی",
            "reminder": "یادآوری"
        }
        
        await message.answer(f"✅ کمپین ایجاد شد!\n\n"
                           f"نام: {data['name']}\n"
                           f"نوع: {type_names.get(data['campaign_type'], data['campaign_type'])}\n"
                           f"شناسه: {campaign.id}")
        
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ خطا در ایجاد کمپین: {str(e)}")


@router.message(Command("process_messages"))
async def process_messages(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            sent_count = await ScheduledMessageService.process_scheduled_messages(session)
        
        await message.answer(f"✅ {sent_count} پیام پردازش شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش پیام‌ها: {str(e)}")


@router.message(Command("process_schedules"))
async def process_schedules(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            executed_count = await ScheduledMessageService.process_recurring_schedules(session)
        
        await message.answer(f"✅ {executed_count} برنامه تکراری اجرا شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش برنامه‌ها: {str(e)}")


@router.message(Command("message_analytics"))
async def message_analytics(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract message ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /message_analytics <message_id>")
        return
    
    try:
        message_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه پیام نامعتبر است.")
        return
    
    async with get_db_session() as session:
        analytics = await ScheduledMessageService.get_message_analytics(session, message_id)
    
    if not analytics:
        await message.answer("آمار پیام یافت نشد.")
        return
    
    analytics_data = analytics["analytics"]
    
    analytics_text = f"""
📊 آمار پیام #{message_id}:

📈 ارسال:
• کل گیرندگان: {analytics_data.total_recipients}
• ارسال شده: {analytics_data.sent_count}
• تحویل داده شده: {analytics_data.delivered_count}
• خوانده شده: {analytics_data.read_count}
• کلیک شده: {analytics_data.clicked_count}
• ناموفق: {analytics_data.failed_count}
• مسدود شده: {analytics_data.blocked_count}

📊 نرخ‌ها:
• نرخ تحویل: {analytics_data.delivery_rate:.1f}%
• نرخ خواندن: {analytics_data.read_rate:.1f}%
• نرخ کلیک: {analytics_data.click_rate:.1f}%
"""
    
    if analytics_data.first_delivery_at:
        analytics_text += f"\n⏰ زمان‌بندی:\n"
        analytics_text += f"• اولین تحویل: {analytics_data.first_delivery_at.strftime('%Y/%m/%d %H:%M')}\n"
        analytics_text += f"• آخرین تحویل: {analytics_data.last_delivery_at.strftime('%Y/%m/%d %H:%M') if analytics_data.last_delivery_at else 'ندارد'}\n"
        if analytics_data.avg_delivery_time:
            analytics_text += f"• میانگین زمان تحویل: {analytics_data.avg_delivery_time} ثانیه\n"
    
    await message.answer(analytics_text)


@router.message(Command("cancel_message"))
async def cancel_message(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract message ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /cancel_message <message_id>")
        return
    
    try:
        message_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه پیام نامعتبر است.")
        return
    
    try:
        async with get_db_session() as session:
            success = await ScheduledMessageService.cancel_scheduled_message(session, message_id)
        
        if success:
            await message.answer(f"✅ پیام #{message_id} لغو شد.")
        else:
            await message.answer(f"❌ نتوانست پیام #{message_id} را لغو کند.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در لغو پیام: {str(e)}")


@router.message(Command("reschedule_message"))
async def reschedule_message(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract message ID and new time from command
    command_parts = message.text.split()
    if len(command_parts) < 3:
        await message.answer("فرمت: /reschedule_message <message_id> <YYYY-MM-DD HH:MM>")
        return
    
    try:
        message_id = int(command_parts[1])
        new_time = datetime.strptime(f"{command_parts[2]} {command_parts[3]}", "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD HH:MM استفاده کنید.")
        return
    
    try:
        async with get_db_session() as session:
            success = await ScheduledMessageService.reschedule_message(session, message_id, new_time)
        
        if success:
            await message.answer(f"✅ پیام #{message_id} برای {new_time.strftime('%Y/%m/%d %H:%M')} زمان‌بندی شد.")
        else:
            await message.answer(f"❌ نتوانست پیام #{message_id} را زمان‌بندی مجدد کند.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در زمان‌بندی مجدد: {str(e)}")


@router.message(Command("scheduled_help"))
async def scheduled_help(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    help_text = """
📨 راهنمای پیام‌های زمان‌بندی شده:

📝 دستورات پیام:
• /create_message - ایجاد پیام زمان‌بندی شده
• /list_messages - لیست پیام‌ها
• /message_analytics <id> - آمار پیام
• /cancel_message <id> - لغو پیام
• /reschedule_message <id> <زمان> - زمان‌بندی مجدد

🏢 دستورات کمپین:
• /create_campaign - ایجاد کمپین
• /list_campaigns - لیست کمپین‌ها
• /campaign_analytics <id> - آمار کمپین

⚙️ دستورات پردازش:
• /process_messages - پردازش پیام‌های آماده
• /process_schedules - پردازش برنامه‌های تکراری

📋 انواع پیام:
• 📝 متن - پیام متنی ساده
• 🖼️ تصویر - پیام با تصویر
• 🎥 ویدیو - پیام با ویدیو
• 📄 سند - پیام با سند

🎯 گروه‌های هدف:
• 👥 همه کاربران - تمام کاربران فعال
• 🎯 کاربران جدید - کاربران 7 روز گذشته
• ⭐ کاربران فعال - کاربران با تعامل بالا
• 💎 کاربران VIP - کاربران با هزینه بالا
• ⚠️ کاربران ترک کرده - کاربران غیرفعال

📊 ویژگی‌ها:
• زمان‌بندی دقیق
• گروه‌بندی هدفمند
• آمارگیری کامل
• برنامه‌های تکراری
• مدیریت کمپین
• لغو و زمان‌بندی مجدد
"""
    
    await message.answer(help_text)