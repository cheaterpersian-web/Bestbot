from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.billing import Transaction
from models.orders import PurchaseIntent
from models.catalog import Plan, Server
from services.purchases import create_service_after_payment
from services.qrcode_gen import generate_qr_with_template
from services.admin_dashboard import AdminDashboardService
from services.payment_processor import PaymentProcessor
from bot.inline import admin_review_tx_kb, admin_manage_servers_kb, admin_manage_categories_kb, admin_manage_plans_kb, admin_transaction_actions_kb, user_profile_actions_kb, broadcast_options_kb
from datetime import datetime
from bot.inline import admin_approve_add_service_kb
import json
from services.scheduled_message_service import ScheduledMessageService
from models.scheduled_messages import MessageType, MessageStatus, ScheduledMessage


router = Router(name="admin")


class ManageUserStates(StatesGroup):
    waiting_user_id = State()


def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 داشبورد"), KeyboardButton(text="📋 بررسی رسیدها")],
            [KeyboardButton(text="👥 مدیریت کاربران"), KeyboardButton(text="🖥️ مدیریت سرورها")],
            [KeyboardButton(text="📁 مدیریت دسته‌ها"), KeyboardButton(text="📦 مدیریت پلن‌ها")],
            [KeyboardButton(text="🎁 سیستم هدیه"), KeyboardButton(text="📢 پیام همگانی")],
            [KeyboardButton(text="🎫 مدیریت تیکت‌ها"), KeyboardButton(text="⚙️ تنظیمات ربات")],
        ],
        resize_keyboard=True,
        input_field_placeholder="یک گزینه ادمین را انتخاب کنید",
    )


async def _is_admin(telegram_id: int) -> bool:
    # runtime check: settings or DB flag
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        return bool(user and user.is_admin)


@router.message(Command("admin"))
async def admin_entry(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("پنل مدیریت:", reply_markup=admin_kb())


@router.message(F.text == "📊 داشبورد")
async def admin_dashboard(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    
    async with get_db_session() as session:
        stats = await AdminDashboardService.get_dashboard_stats(session)
        recent_activities = await AdminDashboardService.get_recent_activities(session, 5)
    
    # Format dashboard text
    text = f"""
📊 داشبورد مدیریت

👥 کاربران:
• کل کاربران: {stats['users']['total']:,}
• کاربران جدید امروز: {stats['users']['new_today']:,}
• کاربران جدید این هفته: {stats['users']['new_week']:,}
• کاربران جدید این ماه: {stats['users']['new_month']:,}
• کاربران فعال امروز: {stats['users']['active_today']:,}
• کاربران مسدود: {stats['users']['blocked']:,}

🔗 سرویس‌ها:
• کل سرویس‌ها: {stats['services']['total']:,}
• سرویس‌های فعال: {stats['services']['active']:,}
• سرویس‌های جدید امروز: {stats['services']['new_today']:,}

💰 درآمد:
• کل درآمد: {stats['revenue']['total']:,.0f} تومان
• درآمد امروز: {stats['revenue']['today']:,.0f} تومان
• درآمد این هفته: {stats['revenue']['week']:,.0f} تومان
• درآمد این ماه: {stats['revenue']['month']:,.0f} تومان

💳 تراکنش‌ها:
• کل تراکنش‌ها: {stats['transactions']['total']:,}
• تراکنش‌های در انتظار: {stats['transactions']['pending']:,}

🎁 دعوت‌ها:
• کل دعوت‌ها: {stats['referrals']['total']:,}
• پاداش پرداخت شده: {stats['referrals']['bonus_paid']:,.0f} تومان

🎫 پشتیبانی:
• تیکت‌های باز: {stats['support']['open_tickets']:,}
• کل تیکت‌ها: {stats['support']['total_tickets']:,}

🖥️ زیرساخت:
• سرورها: {stats['infrastructure']['servers']['active']}/{stats['infrastructure']['servers']['total']}
• دسته‌ها: {stats['infrastructure']['categories']['active']}/{stats['infrastructure']['categories']['total']}
• پلن‌ها: {stats['infrastructure']['plans']['active']}/{stats['infrastructure']['plans']['total']}
    """.strip()
    
    await message.answer(text)
    
    # Show recent activities
    if recent_activities:
        activities_text = "\n🕐 آخرین فعالیت‌ها:\n"
        for activity in recent_activities:
            timestamp = activity['timestamp'].strftime("%H:%M")
            if activity['type'] == 'new_user':
                data = activity['data']
                activities_text += f"• {timestamp} - کاربر جدید: {data['first_name']} (@{data['username'] or 'بدون نام کاربری'})\n"
            elif activity['type'] == 'transaction':
                data = activity['data']
                activities_text += f"• {timestamp} - تراکنش: {data['amount']:,.0f} تومان ({data['type']})\n"
            elif activity['type'] == 'new_service':
                data = activity['data']
                activities_text += f"• {timestamp} - سرویس جدید: {data['remark']}\n"
        
        await message.answer(activities_text)


class BroadcastStates(StatesGroup):
    choosing_type = State()
    waiting_text = State()
    waiting_photo = State()
    waiting_caption = State()
    waiting_forward = State()
    waiting_schedule = State()
    choosing_target = State()
    confirming = State()


def _broadcast_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 همه کاربران", callback_data="bc_target:all")],
            [InlineKeyboardButton(text="🎯 کاربران جدید", callback_data="bc_target:new_users")],
            [InlineKeyboardButton(text="⭐ کاربران فعال", callback_data="bc_target:active_users")],
            [InlineKeyboardButton(text="💎 کاربران VIP", callback_data="bc_target:vip_users")],
            [InlineKeyboardButton(text="⚠️ کاربران ترک کرده", callback_data="bc_target:churned_users")],
        ]
    )


def _broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید و ارسال", callback_data="bc_confirm:yes"),
                InlineKeyboardButton(text="❌ انصراف", callback_data="bc_confirm:no"),
            ]
        ]
    )


@router.message(F.text == "📢 پیام همگانی")
async def admin_broadcast(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await state.clear()
    await state.set_state(BroadcastStates.choosing_type)
    await message.answer(
        "نوع پیام همگانی را انتخاب کنید:",
        reply_markup=broadcast_options_kb(),
    )


@router.callback_query(F.data == "broadcast:text")
async def bc_choose_text(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await state.update_data(message_type="text")
    await state.set_state(BroadcastStates.waiting_text)
    await callback.message.edit_text("متن پیام را ارسال کنید:")
    await callback.answer()


@router.callback_query(F.data == "broadcast:image")
async def bc_choose_image(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await state.update_data(message_type="image")
    await state.set_state(BroadcastStates.waiting_photo)
    await callback.message.edit_text("تصویر را ارسال کنید:")
    await callback.answer()


@router.callback_query(F.data == "broadcast:forward")
async def bc_choose_forward(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await state.update_data(message_type="forward")
    await state.set_state(BroadcastStates.waiting_forward)
    await callback.message.edit_text("پیامی را که می‌خواهید همگانی شود، اینجا فوروارد یا ریپلای کنید:")
    await callback.answer()


@router.callback_query(F.data == "broadcast:stats")
async def bc_stats(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    async with get_db_session() as session:
        from sqlalchemy import select, desc
        admin_user = (
            await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
            )
        ).scalar_one_or_none()
        messages = (
            await session.execute(
                select(ScheduledMessage)
                .where(ScheduledMessage.created_by == (admin_user.id if admin_user else 0))
                .order_by(desc(ScheduledMessage.created_at))
                .limit(5)
            )
        ).scalars().all()
    if not messages:
        await callback.message.edit_text("هیچ پیام همگانی اخیر یافت نشد.")
        await callback.answer()
        return
    status_emojis = {
        MessageStatus.DRAFT: "📝",
        MessageStatus.SCHEDULED: "⏰",
        MessageStatus.SENDING: "📤",
        MessageStatus.SENT: "✅",
        MessageStatus.FAILED: "❌",
        MessageStatus.CANCELLED: "🚫",
    }
    type_emojis = {
        MessageType.TEXT: "📝",
        MessageType.IMAGE: "🖼️",
        MessageType.VIDEO: "🎥",
        MessageType.DOCUMENT: "📄",
    }
    text = "📊 آخرین پیام‌های همگانی:\n\n"
    for m in messages:
        text += f"{status_emojis.get(m.status, '❓')} {type_emojis.get(m.message_type, '❓')} {m.title}\n"
        text += f"   زمان: {m.scheduled_at.strftime('%Y/%m/%d %H:%M')}\n"
        text += f"   گیرندگان: {m.total_recipients} | ارسال‌شده: {m.sent_count}\n\n"
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(BroadcastStates.waiting_text)
async def bc_receive_text(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    content = (message.text or "").strip()
    if not content:
        await message.answer("متن نامعتبر است. لطفاً دوباره ارسال کنید.")
        return
    await state.update_data(content=content, title=content[:50])
    await state.set_state(BroadcastStates.waiting_schedule)
    await message.answer("زمان ارسال را وارد کنید (الان یا YYYY-MM-DD HH:MM):")


@router.message(BroadcastStates.waiting_photo)
async def bc_receive_photo(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    if not message.photo:
        await message.answer("لطفاً یک تصویر ارسال کنید.")
        return
    photo_file_id = message.photo[-1].file_id
    await state.update_data(media_file_id=photo_file_id)
    await state.set_state(BroadcastStates.waiting_caption)
    await message.answer("کپشن (عنوان/متن) را ارسال کنید:")


@router.message(BroadcastStates.waiting_caption)
async def bc_receive_caption(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    caption = (message.text or "").strip()
    if not caption:
        await message.answer("کپشن نامعتبر است. لطفاً دوباره ارسال کنید.")
        return
    await state.update_data(content=caption, title=caption[:50])
    await state.set_state(BroadcastStates.waiting_schedule)
    await message.answer("زمان ارسال را وارد کنید (الان یا YYYY-MM-DD HH:MM):")


@router.message(BroadcastStates.waiting_forward)
async def bc_receive_forward(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    # Store source chat and message id to copy later
    from_chat_id = message.chat.id
    source_message_id = message.message_id
    # Optional: allow custom caption override via reply? For now, keep empty
    await state.update_data(forward_ref={"from_chat_id": from_chat_id, "message_id": source_message_id}, title=f"Forward #{source_message_id}")
    await state.set_state(BroadcastStates.waiting_schedule)
    await message.answer("زمان ارسال را وارد کنید (الان یا YYYY-MM-DD HH:MM):")


@router.message(BroadcastStates.waiting_schedule)
async def bc_receive_schedule(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    scheduled_at = None
    if text in {"الان", "اکنون", "همین الان", "now", "immediately"}:
        scheduled_at = datetime.utcnow()
    else:
        try:
            scheduled_at = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD HH:MM یا 'الان' استفاده کنید.")
            return
    await state.update_data(scheduled_at=scheduled_at)
    await state.set_state(BroadcastStates.choosing_target)
    await message.answer("گروه هدف را انتخاب کنید:", reply_markup=_broadcast_target_kb())


@router.callback_query(F.data.startswith("bc_target:"))
async def bc_choose_target(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    target_key = callback.data.split(":")[1]
    await state.update_data(target=target_key)
    data = await state.get_data()
    # Estimate recipients count
    try:
        async with get_db_session() as session:
            recipients = await ScheduledMessageService._generate_recipient_list(
                session=session,
                target_type="all" if target_key == "all" else "segment",
                target_users=None,
                target_segments=None if target_key == "all" else [target_key],
            )
            recipients_count = len(recipients)
    except Exception:
        recipients_count = 0
    await state.update_data(recipients_count=recipients_count)

    # Build preview text
    mt = data.get("message_type")
    type_name = "متن" if mt == "text" else ("تصویر" if mt == "image" else "فوروارد")
    target_names = {
        "all": "همه کاربران",
        "new_users": "کاربران جدید",
        "active_users": "کاربران فعال",
        "vip_users": "کاربران VIP",
        "churned_users": "کاربران ترک کرده",
    }
    preview = (
        f"پیش‌نمایش پیام همگانی:\n\n"
        f"عنوان: {data.get('title','')}\n"
        f"نوع: {type_name}\n"
        f"زمان ارسال: {data.get('scheduled_at').strftime('%Y/%m/%d %H:%M')}\n"
        f"گروه هدف: {target_names.get(target_key, target_key)}\n"
        f"تخمینی گیرندگان: {recipients_count}\n\n"
        f"— متن —\n{data.get('content','')}"
    )
    try:
        await callback.message.edit_text(preview, reply_markup=_broadcast_confirm_kb())
    except Exception:
        await callback.message.answer(preview, reply_markup=_broadcast_confirm_kb())
    await state.set_state(BroadcastStates.confirming)
    await callback.answer()


@router.callback_query(F.data.startswith("bc_confirm:"))
async def bc_confirm(callback: CallbackQuery, state: FSMContext):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    choice = callback.data.split(":")[1]
    if choice == "no":
        await state.clear()
        await callback.message.edit_text("لغو شد.")
        await callback.answer()
        return

    data = await state.get_data()
    await state.clear()
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (
                await session.execute(
                    select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
                )
            ).scalar_one_or_none()

            target_type = "all" if data.get("target") == "all" else "segment"
            target_segments = None if target_type == "all" else [data.get("target")]

            # Build content depending on type
            if data.get("message_type") == "forward":
                content_payload = json.dumps(data.get("forward_ref"))
                msg_type = MessageType.FORWARD
            else:
                content_payload = data.get("content", "")
                msg_type = MessageType.TEXT if data.get("message_type") == "text" else MessageType.IMAGE

            message = await ScheduledMessageService.create_scheduled_message(
                session=session,
                title=data.get("title", "Broadcast"),
                content=content_payload,
                scheduled_at=data.get("scheduled_at", datetime.utcnow()),
                message_type=msg_type,
                target_type=target_type,
                target_users=None,
                target_segments=target_segments,
                created_by=admin_user.id if admin_user else 0,
                media_file_id=data.get("media_file_id"),
                media_caption=data.get("content") if data.get("message_type") in {"text", "image"} else None,
            )

            # Mark as scheduled
            message.status = MessageStatus.SCHEDULED

            # If immediate, try to process right away
            if message.scheduled_at <= datetime.utcnow():
                await ScheduledMessageService.process_scheduled_messages(session)

        await callback.message.edit_text(
            f"✅ پیام همگانی ثبت شد.\n"
            f"گیرندگان: {message.total_recipients}\n"
            f"زمان ارسال: {message.scheduled_at.strftime('%Y/%m/%d %H:%M')}"
        )
        await callback.answer()
    except Exception as e:
        await callback.message.edit_text(f"❌ خطا در ثبت/ارسال پیام: {str(e)}")
        await callback.answer()


@router.message(F.text == "🖥️ مدیریت سرورها")
async def admin_manage_servers(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("مدیریت سرورها:", reply_markup=admin_manage_servers_kb())


@router.message(F.text == "📁 مدیریت دسته‌ها")
async def admin_manage_categories(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("مدیریت دسته‌ها:", reply_markup=admin_manage_categories_kb())


@router.message(F.text == "📦 مدیریت پلن‌ها")
async def admin_manage_plans(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("مدیریت پلن‌ها:", reply_markup=admin_manage_plans_kb())


@router.message(F.text == "👥 مدیریت کاربران")
async def admin_manage_users(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await state.set_state(ManageUserStates.waiting_user_id)
    await message.answer(
        "👥 مدیریت کاربران\n\nبرای مدیریت کاربران، شناسه کاربری (User ID) را ارسال کنید.\n\nلغو: ارسال کنید 'لغو'",
    )


@router.message(ManageUserStates.waiting_user_id, F.text.regexp(r"^\d+$"))
async def admin_user_lookup(message: Message, state: FSMContext):
    """Handle user ID lookup for admin management"""
    if not await _is_admin(message.from_user.id):
        return
    
    user_id = int(message.text)
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await message.answer("❌ کاربر یافت نشد.")
            await state.clear()
            return
        
        # Get user statistics
        user_stats = await AdminDashboardService.get_user_stats(session, user.id)
        
        text = f"""
👤 اطلاعات کاربر

🆔 شناسه: {user.telegram_user_id}
👤 نام: {user.first_name or 'بدون نام'} {user.last_name or ''}
📱 نام کاربری: @{user.username or 'بدون نام کاربری'}
💰 موجودی: {user.wallet_balance:,.0f} تومان
🔒 وضعیت: {'مسدود' if user.is_blocked else 'فعال'}
📅 عضویت: {user.created_at.strftime('%Y/%m/%d')}
🕐 آخرین بازدید: {user.last_seen_at.strftime('%Y/%m/%d %H:%M') if user.last_seen_at else 'هرگز'}

📊 آمار:
🔗 سرویس‌ها: {user_stats['services']['total']} (فعال: {user_stats['services']['active']})
💳 تراکنش‌ها: {user_stats['transactions']['total']}
👥 دعوت‌ها: {user_stats['referrals']['made']}
💰 درآمد از دعوت: {user_stats['referrals']['earnings']:,.0f} تومان
        """.strip()
        
        await message.answer(text, reply_markup=user_profile_actions_kb(user.telegram_user_id))
    await state.clear()


@router.message(ManageUserStates.waiting_user_id, F.text.regexp(r"^(لغو|انصراف|cancel|Cancel|CANCEL)$"))
async def admin_user_lookup_cancel(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("لغو شد. به پنل مدیریت بازگشتید.", reply_markup=admin_kb())


@router.message(F.text == "🎁 سیستم هدیه")
async def admin_gift_system(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "🎫 مدیریت تیکت‌ها")
async def admin_manage_tickets(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "⚙️ تنظیمات ربات")
async def admin_bot_settings(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")


@router.message(F.text == "📋 بررسی رسیدها")
async def admin_review_menu(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        txs = (
            await session.execute(
                select(Transaction).where(
                    Transaction.status == "pending",
                    Transaction.type.in_(["purchase", "wallet_topup"]),
                )
            )
        ).scalars().all()
    if not txs:
        await message.answer("هیچ رسید در انتظاری وجود ندارد.")
        return
    for tx in txs:
        # Get user info for better display
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == tx.user_id)
        )).scalar_one_or_none()
        
        user_info = f"{user.first_name or 'بدون نام'}" if user else f"ID:{tx.user_id}"
        fraud_info = f"\n🚨 Fraud Score: {tx.fraud_score:.2f}" if tx.fraud_score > 0 else ""
        
        caption = f"📋 TX#{tx.id} | نوع: {tx.type} | مبلغ: {int(tx.amount):,} تومان\n👤 کاربر: {user_info} (ID: {tx.user_id}){fraud_info}"
        
        if tx.receipt_image_file_id:
            try:
                await message.answer_photo(photo=tx.receipt_image_file_id, caption=caption, reply_markup=admin_transaction_actions_kb(tx.id))
            except Exception:
                await message.answer(caption, reply_markup=admin_transaction_actions_kb(tx.id))
        else:
            await message.answer(caption, reply_markup=admin_transaction_actions_kb(tx.id))


@router.callback_query(F.data.startswith("admin:approve_tx:"))
async def cb_approve_tx(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    tx_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await callback.answer("یافت نشد/در انتظار نیست", show_alert=True)
            return
        
        admin_db_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id))
        ).scalar_one_or_none()
        
        # Use payment processor to approve transaction
        success = await PaymentProcessor.approve_transaction(
            session, tx, admin_db_user.id if admin_db_user else callback.from_user.id, "تایید دستی توسط ادمین"
        )
        
        if not success:
            await callback.answer("خطا در تایید تراکنش", show_alert=True)
            return

    created_service = None
    user = None
    # For receipt-based purchases, tx.type is usually 'purchase_receipt'
    if tx.type in {"purchase", "purchase_receipt"}:
        intent = (
            await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
        ).scalar_one_or_none()
        if intent:
            plan = (await session.execute(select(Plan).where(Plan.id == intent.plan_id))).scalar_one()
            server = (await session.execute(select(Server).where(Server.id == intent.server_id))).scalar_one()
            user = (await session.execute(select(TelegramUser).where(TelegramUser.id == intent.user_id))).scalar_one()
            intent.status = "paid"
            # Prefer alias stored on intent if present
            remark = intent.alias or f"u{user.id}-{plan.title}"
            created_service = await create_service_after_payment(session, user, plan, server, remark=remark)

    # notify user and update wallet if needed
    if tx.type in {"purchase", "purchase_receipt"} and created_service and user:
        qr_bytes = generate_qr_with_template(created_service.subscription_url)
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text="✅ خرید شما تایید شد. لینک اتصال:")
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=created_service.subscription_url)
        await callback.message.bot.send_photo(chat_id=user.telegram_user_id, photo=BufferedInputFile(qr_bytes, filename="sub.png"), caption="QR اتصال")
    elif tx.type == "wallet_topup":
        # Wallet balance is already updated by PaymentProcessor
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()
        if user:
            await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=f"✅ شارژ کیف پول تایید شد. مبلغ {int(tx.amount):,} تومان افزوده شد.")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("تایید شد")


@router.callback_query(F.data.startswith("admin:reject_tx:"))
async def cb_reject_tx(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    tx_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await callback.answer("یافت نشد/در انتظار نیست", show_alert=True)
            return
        
        admin_db_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id))
        ).scalar_one_or_none()
        
        # Use payment processor to reject transaction
        success = await PaymentProcessor.reject_transaction(
            session, tx, admin_db_user.id if admin_db_user else callback.from_user.id, "رد توسط ادمین"
        )
        
        if not success:
            await callback.answer("خطا در رد تراکنش", show_alert=True)
            return
        
        if tx.type == "purchase":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                intent.status = "cancelled"
        
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()

    if user:
        await callback.message.bot.send_message(chat_id=user.telegram_user_id, text=f"❌ رسید شما رد شد. لطفاً با پشتیبانی تماس بگیرید.")
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("رد شد")


@router.message(Command("pending"))
async def list_pending_receipts(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    async with get_db_session() as session:
        from sqlalchemy import select
        txs = (
            await session.execute(select(Transaction).where(Transaction.type == "purchase_receipt", Transaction.status == "pending"))
        ).scalars().all()
    if not txs:
        await message.answer("رسید در انتظار تایید یافت نشد.")
        return
    for tx in txs:
        await message.answer(
            f"TX#{tx.id} | مبلغ: {int(tx.amount):,} | کاربر: {tx.user_id}\nبرای تایید از دکمه‌های اختصاصی (در نسخه بعد) یا دستورات دستی استفاده کنید."
        )


@router.message(Command("reply_ticket"))
async def admin_reply_ticket(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    # format: /reply_ticket <ticket_id> <text>
    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("فرمت: /reply_ticket <ticket_id> <متن>")
        return
    ticket_id = int(parts[1])
    body = parts[2]
    async with get_db_session() as session:
        from sqlalchemy import select
        t = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        if not t:
            await message.answer("تیکت یافت نشد.")
            return
        admin_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one_or_none()
        session.add(TicketMessage(ticket_id=ticket_id, sender_user_id=admin_user.id if admin_user else 0, body=body, by_admin=True))
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == t.user_id))).scalar_one_or_none()
    if user:
        await message.bot.send_message(chat_id=user.telegram_user_id, text=f"پاسخ پشتیبانی: {body}")
    await message.answer("ارسال شد.")


@router.message(Command("close_ticket"))
async def admin_close_ticket(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("فرمت: /close_ticket <ticket_id>")
        return
    ticket_id = int(parts[1])
    async with get_db_session() as session:
        from sqlalchemy import select
        t = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one_or_none()
        if not t:
            await message.answer("تیکت یافت نشد.")
            return
        t.status = "closed"
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == t.user_id))).scalar_one_or_none()
    if user:
        await message.bot.send_message(chat_id=user.telegram_user_id, text=f"تیکت #{ticket_id} بسته شد.")
    await message.answer("بسته شد.")


@router.message(F.text.regexp(r"^/approve_tx\s+\d+$"))
async def approve_tx(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    parts = message.text.strip().split()
    tx_id = int(parts[1])
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await message.answer("تراکنش معتبر یا در انتظار یافت نشد.")
            return
        admin_db_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one_or_none()

        tx.status = "approved"
        if admin_db_user:
            tx.approved_by_admin_id = admin_db_user.id
        tx.approved_at = datetime.utcnow()

        # purchase receipt: create service
        created_service = None
        if tx.type == "purchase_receipt":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                plan = (await session.execute(select(Plan).where(Plan.id == intent.plan_id))).scalar_one()
                server = (await session.execute(select(Server).where(Server.id == intent.server_id))).scalar_one()
                user = (await session.execute(select(TelegramUser).where(TelegramUser.id == intent.user_id))).scalar_one()
                intent.status = "paid"
                created_service = await create_service_after_payment(session, user, plan, server, remark=f"u{user.id}-{plan.title}")

    # notify user
    if tx.type == "purchase_receipt" and created_service:
        qr_bytes = generate_qr_with_template(created_service.subscription_url)
        await message.bot.send_message(chat_id=user.telegram_user_id, text="خرید شما تایید شد. لینک اتصال:")
        await message.bot.send_message(chat_id=user.telegram_user_id, text=created_service.subscription_url)
        await message.bot.send_photo(chat_id=user.telegram_user_id, photo=BufferedInputFile(qr_bytes, filename="sub.png"), caption="QR اتصال")
        await message.answer(f"TX#{tx_id} تایید شد و سرویس ساخته شد.")
    elif tx.type == "wallet_topup":
        # update wallet balance now that approved
        async with get_db_session() as session:
            from sqlalchemy import select
            me = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()
            if me:
                me.wallet_balance = (me.wallet_balance or 0) + int(tx.amount)
        if me:
            await message.bot.send_message(chat_id=me.telegram_user_id, text=f"شارژ کیف پول تایید شد. مبلغ {int(tx.amount):,} تومان افزوده شد.")
        await message.answer(f"TX#{tx_id} شارژ کیف تایید شد.")


@router.message(F.text.regexp(r"^/reject_tx\s+\d+(\s+.*)?$"))
async def reject_tx(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    parts = message.text.strip().split(maxsplit=2)
    tx_id = int(parts[1])
    reason = parts[2] if len(parts) > 2 else "رسید نامعتبر"
    async with get_db_session() as session:
        from sqlalchemy import select
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalar_one_or_none()
        if not tx or tx.status != "pending":
            await message.answer("تراکنش معتبر یا در انتظار یافت نشد.")
            return
        tx.status = "rejected"
        if tx.type == "purchase_receipt":
            intent = (
                await session.execute(select(PurchaseIntent).where(PurchaseIntent.receipt_transaction_id == tx.id))
            ).scalar_one_or_none()
            if intent:
                intent.status = "cancelled"
        user = (await session.execute(select(TelegramUser).where(TelegramUser.id == tx.user_id))).scalar_one_or_none()

    if user:
        await message.bot.send_message(chat_id=user.telegram_user_id, text=f"رسید شما رد شد. علت: {reason}")
    await message.answer(f"TX#{tx_id} رد شد.")


@router.callback_query(F.data.startswith("admin:approve_addsvc:"))
async def approve_add_service(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    _, _, svc_id_str, tg_user_id_str = callback.data.split(":")
    svc_id = int(svc_id_str)
    tg_user_id = int(tg_user_id_str)
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        user = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == tg_user_id))).scalar_one_or_none()
        if not svc or not user:
            await callback.answer("یافت نشد", show_alert=True)
            return
        svc.user_id = user.id
    await callback.message.answer(f"سرویس #{svc_id} به کاربر {tg_user_id} منتقل شد.")
    await callback.answer("انجام شد")


@router.callback_query(F.data.startswith("admin:reject_addsvc:"))
async def reject_add_service(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    await callback.message.answer("درخواست انتقال رد شد.")
    await callback.answer("رد شد")


@router.callback_query(F.data.startswith("admin:block_user:"))
async def cb_block_user(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await callback.answer("کاربر یافت نشد", show_alert=True)
            return
        
        user.is_blocked = True
        await session.commit()
    
    await callback.answer("کاربر مسدود شد")
    await callback.message.edit_text(
        callback.message.text + "\n\n🔒 کاربر مسدود شد.",
        reply_markup=user_profile_actions_kb(user_id)
    )


@router.callback_query(F.data.startswith("admin:unblock_user:"))
async def cb_unblock_user(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await callback.answer("کاربر یافت نشد", show_alert=True)
            return
        
        user.is_blocked = False
        await session.commit()
    
    await callback.answer("کاربر آزاد شد")
    await callback.message.edit_text(
        callback.message.text + "\n\n🔓 کاربر آزاد شد.",
        reply_markup=user_profile_actions_kb(user_id)
    )


@router.callback_query(F.data.startswith("admin:user_stats:"))
async def cb_user_stats(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("اجازه ندارید", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[-1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await callback.answer("کاربر یافت نشد", show_alert=True)
            return
        
        user_stats = await AdminDashboardService.get_user_stats(session, user.id)
        
        # Get detailed transaction history
        transactions = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )).scalars().all()
        
        stats_text = f"""
📊 آمار تفصیلی کاربر {user.first_name or 'بدون نام'}

💰 موجودی فعلی: {user.wallet_balance:,.0f} تومان
🔗 کل سرویس‌ها: {user_stats['services']['total']}
🔗 سرویس‌های فعال: {user_stats['services']['active']}
💳 کل تراکنش‌ها: {user_stats['transactions']['total']}
👥 دعوت‌ها: {user_stats['referrals']['made']}
💰 درآمد از دعوت: {user_stats['referrals']['earnings']:,.0f} تومان

📝 آخرین تراکنش‌ها:
        """.strip()
        
        for tx in transactions:
            status_emoji = "✅" if tx.status == "approved" else "⏳" if tx.status == "pending" else "❌"
            date_str = tx.created_at.strftime("%m/%d %H:%M")
            stats_text += f"\n{status_emoji} {tx.amount:,.0f} تومان - {tx.type} ({date_str})"
    
    await callback.message.answer(stats_text)


# Additional Admin Features
@router.message(Command("admin_commands"))
async def admin_commands_help(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    commands_text = """
🔧 دستورات ادمین:

📊 مدیریت کاربران:
• /admin - پنل ادمین
• /user_info <user_id> - اطلاعات کاربر
• /block_user <user_id> - مسدود کردن کاربر
• /unblock_user <user_id> - رفع مسدودیت کاربر

💰 مدیریت مالی:
• /wallet_adjust <user_id> <amount> - تنظیم موجودی کیف پول
• /transaction_stats - آمار تراکنش‌ها
• /pending_transactions - تراکنش‌های در انتظار

🖥️ مدیریت سرورها:
• /add_server - اضافه کردن سرور
• /list_servers - لیست سرورها
• /server_status - وضعیت سرورها

📦 مدیریت پلن‌ها:
• /add_plan - اضافه کردن پلن
• /list_plans - لیست پلن‌ها
• /plan_stats - آمار پلن‌ها

🎁 سیستم هدیه:
• /gift_wallet <user_id> <amount> - هدیه موجودی
• /gift_traffic <user_id> <gb> - هدیه ترافیک
• /bulk_gift - هدیه گروهی

🎫 مدیریت تیکت‌ها:
• /ticket_list - لیست تیکت‌ها
• /ticket_reply <ticket_id> - پاسخ به تیکت

📢 پیام‌رسانی:
• /broadcast - ارسال پیام همگانی
• /broadcast_image - ارسال تصویر همگانی

🔧 تنظیمات:
• /bot_settings - تنظیمات ربات
• /payment_settings - تنظیمات پرداخت
• /trial_config - تنظیمات تست

📊 گزارش‌گیری:
• /daily_report - گزارش روزانه
• /weekly_report - گزارش هفتگی
• /monthly_report - گزارش ماهانه
• /user_analytics - آمار کاربران

🎁 کدهای تخفیف:
• /add_discount - اضافه کردن کد تخفیف
• /list_discounts - لیست کدهای تخفیف
• /discount_stats - آمار کدهای تخفیف

🤝 نمایندگان:
• /reseller_requests - درخواست‌های نمایندگی
• /list_resellers - لیست نمایندگان
• /reseller_stats - آمار نمایندگان

🧪 سیستم تست:
• /trial_requests - درخواست‌های تست
• /trial_config - تنظیمات تست

🔗 دکمه‌ها:
• /add_button - اضافه کردن دکمه
• /list_buttons - لیست دکمه‌ها
• /toggle_button - تغییر وضعیت دکمه
"""
    
    await message.answer(commands_text)


@router.message(Command("daily_report"))
async def daily_report(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        from datetime import datetime, timedelta
        
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        # Daily statistics
        new_users = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.created_at >= yesterday)
        )).scalar()
        
        new_services = (await session.execute(
            select(func.count(Service.id))
            .where(Service.purchased_at >= yesterday)
        )).scalar()
        
        daily_revenue = (await session.execute(
            select(func.sum(Transaction.amount))
            .where(Transaction.status == "approved")
            .where(Transaction.created_at >= yesterday)
        )).scalar() or 0
        
        pending_transactions = (await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.status == "pending")
        )).scalar()
        
        active_services = (await session.execute(
            select(func.count(Service.id))
            .where(Service.is_active == True)
        )).scalar()
        
        expired_services = (await session.execute(
            select(func.count(Service.id))
            .where(Service.expires_at < datetime.utcnow())
            .where(Service.is_active == True)
        )).scalar()
    
    report_text = f"""
📊 گزارش روزانه - {today.strftime('%Y/%m/%d')}

👥 کاربران جدید: {new_users}
🆕 سرویس‌های جدید: {new_services}
💰 درآمد روزانه: {daily_revenue:,.0f} تومان
⏳ تراکنش‌های در انتظار: {pending_transactions}
✅ سرویس‌های فعال: {active_services}
❌ سرویس‌های منقضی: {expired_services}

📈 وضعیت کلی:
• رشد کاربران: {'📈' if new_users > 0 else '📉'}
• رشد درآمد: {'📈' if daily_revenue > 0 else '📉'}
• نیاز به بررسی: {'⚠️' if pending_transactions > 0 else '✅'}
"""
    
    await message.answer(report_text)


@router.message(Command("user_analytics"))
async def user_analytics(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        from datetime import datetime, timedelta
        
        # User analytics
        total_users = (await session.execute(
            select(func.count(TelegramUser.id))
        )).scalar()
        
        active_users = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.last_seen_at >= datetime.utcnow() - timedelta(days=7))
        )).scalar()
        
        verified_users = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.is_verified == True)
        )).scalar()
        
        blocked_users = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.is_blocked == True)
        )).scalar()
        
        users_with_services = (await session.execute(
            select(func.count(func.distinct(Service.user_id)))
        )).scalar()
        
        avg_wallet_balance = (await session.execute(
            select(func.avg(TelegramUser.wallet_balance))
        )).scalar() or 0
        
        total_spent = (await session.execute(
            select(func.sum(TelegramUser.total_spent))
        )).scalar() or 0
    
    analytics_text = f"""
📊 آمار کاربران:

👥 کل کاربران: {total_users:,}
✅ کاربران فعال (7 روز): {active_users:,}
🔐 کاربران تایید شده: {verified_users:,}
🚫 کاربران مسدود: {blocked_users:,}
🛒 کاربران با سرویس: {users_with_services:,}

💰 آمار مالی:
• میانگین موجودی: {avg_wallet_balance:,.0f} تومان
• کل خریدها: {total_spent:,.0f} تومان
• میانگین خرید: {total_spent / max(users_with_services, 1):,.0f} تومان

📈 نرخ‌ها:
• نرخ فعال بودن: {(active_users / max(total_users, 1) * 100):.1f}%
• نرخ تایید: {(verified_users / max(total_users, 1) * 100):.1f}%
• نرخ خرید: {(users_with_services / max(total_users, 1) * 100):.1f}%
"""
    
    await message.answer(analytics_text)


@router.message(Command("server_status"))
async def server_status(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        
        servers = (await session.execute(
            select(Server).order_by(Server.sort_order)
        )).scalars().all()
    
    if not servers:
        await message.answer("سروری ثبت نشده است.")
        return
    
    status_text = "🖥️ وضعیت سرورها:\n\n"
    
    for server in servers:
        status_emoji = "✅" if server.is_active else "❌"
        sync_emoji = {
            "success": "✅",
            "error": "❌",
            "syncing": "🔄",
            "unknown": "❓"
        }.get(server.sync_status, "❓")
        
        connections_info = f"{server.current_connections}"
        if server.max_connections:
            connections_info += f"/{server.max_connections}"
        
        status_text += f"{status_emoji} {server.name}\n"
        status_text += f"   نوع: {server.panel_type}\n"
        status_text += f"   اتصالات: {connections_info}\n"
        status_text += f"   همگام‌سازی: {sync_emoji} {server.sync_status}\n"
        if server.last_sync_at:
            status_text += f"   آخرین همگام‌سازی: {server.last_sync_at.strftime('%m/%d %H:%M')}\n"
        if server.error_message:
            status_text += f"   خطا: {server.error_message[:50]}...\n"
        status_text += "\n"
    
    await message.answer(status_text)


@router.message(Command("plan_stats"))
async def plan_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        
        # Plan statistics
        total_plans = (await session.execute(
            select(func.count(Plan.id))
        )).scalar()
        
        active_plans = (await session.execute(
            select(func.count(Plan.id))
            .where(Plan.is_active == True)
        )).scalar()
        
        popular_plans = (await session.execute(
            select(func.count(Plan.id))
            .where(Plan.is_popular == True)
        )).scalar()
        
        recommended_plans = (await session.execute(
            select(func.count(Plan.id))
            .where(Plan.is_recommended == True)
        )).scalar()
        
        # Top selling plans
        top_plans = (await session.execute(
            select(Plan.title, Plan.sales_count)
            .order_by(Plan.sales_count.desc())
            .limit(5)
        )).all()
        
        # Average price
        avg_price = (await session.execute(
            select(func.avg(Plan.price_irr))
        )).scalar() or 0
    
    stats_text = f"""
📦 آمار پلن‌ها:

📊 کلی:
• کل پلن‌ها: {total_plans}
• پلن‌های فعال: {active_plans}
• پلن‌های محبوب: {popular_plans}
• پلن‌های پیشنهادی: {recommended_plans}
• میانگین قیمت: {avg_price:,.0f} تومان

🏆 پرفروش‌ترین پلن‌ها:
"""
    
    for i, (title, sales) in enumerate(top_plans, 1):
        stats_text += f"{i}. {title}: {sales} فروش\n"
    
    await message.answer(stats_text)


