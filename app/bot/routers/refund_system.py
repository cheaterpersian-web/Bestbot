from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.refund_system import RefundType, RefundStatus, RefundReason
from services.refund_service import RefundService


router = Router(name="refund_system")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class RefundRequestStates(StatesGroup):
    waiting_service = State()
    waiting_reason = State()
    waiting_amount = State()
    waiting_description = State()


class UpgradeRequestStates(StatesGroup):
    waiting_service = State()
    waiting_plan = State()
    waiting_payment = State()


# User-side refund features
@router.message(Command("request_refund"))
async def request_refund_start(message: Message, state: FSMContext):
    """Start refund request process"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        # Get user's active services
        from models.service import Service
        services = (await session.execute(
            select(Service)
            .where(
                and_(
                    Service.user_id == user.id,
                    Service.is_active == True
                )
            )
        )).scalars().all()
        
        if not services:
            await message.answer("شما هیچ سرویس فعالی ندارید.")
            return
    
    # Show services for selection
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for service in services[:10]:  # Limit to 10 services
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"سرویس {service.id} - {service.remark or 'بدون توضیح'}",
                callback_data=f"refund_service:{service.id}"
            )
        ])
    
    await message.answer("سرویسی که می‌خواهید بازپرداخت کنید را انتخاب کنید:", reply_markup=kb)
    await state.set_state(RefundRequestStates.waiting_service)


@router.callback_query(F.data.startswith("refund_service:"))
async def refund_service_selected(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RefundRequestStates.waiting_service:
        return
    
    service_id = int(callback.data.split(":")[1])
    await state.update_data(service_id=service_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="درخواست کاربر", callback_data="refund_reason:user_request")],
        [InlineKeyboardButton(text="مشکل سرویس", callback_data="refund_reason:service_issue")],
        [InlineKeyboardButton(text="مشکل فنی", callback_data="refund_reason:technical_problem")],
        [InlineKeyboardButton(text="خطای صورتحساب", callback_data="refund_reason:billing_error")],
        [InlineKeyboardButton(text="مشکل کیفیت", callback_data="refund_reason:quality_issue")]
    ])
    
    await callback.message.edit_text("دلیل بازپرداخت را انتخاب کنید:", reply_markup=kb)
    await state.set_state(RefundRequestStates.waiting_reason)
    await callback.answer()


@router.callback_query(F.data.startswith("refund_reason:"))
async def refund_reason_selected(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RefundRequestStates.waiting_reason:
        return
    
    reason = callback.data.split(":")[1]
    await state.update_data(refund_reason=reason)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="بازپرداخت کامل", callback_data="refund_type:full_refund")],
        [InlineKeyboardButton(text="بازپرداخت جزئی", callback_data="refund_type:partial_refund")],
        [InlineKeyboardButton(text="اعتبار کیف پول", callback_data="refund_type:wallet_credit")]
    ])
    
    await callback.message.edit_text("نوع بازپرداخت را انتخاب کنید:", reply_markup=kb)
    await state.set_state(RefundRequestStates.waiting_amount)
    await callback.answer()


@router.callback_query(F.data.startswith("refund_type:"))
async def refund_type_selected(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != RefundRequestStates.waiting_amount:
        return
    
    refund_type = callback.data.split(":")[1]
    await state.update_data(refund_type=refund_type)
    
    await callback.message.edit_text("مبلغ بازپرداخت را وارد کنید (تومان):")
    await state.set_state(RefundRequestStates.waiting_description)
    await callback.answer()


@router.message(RefundRequestStates.waiting_description)
async def refund_amount_and_description(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("لطفاً مبلغ معتبر وارد کنید.")
        return
    
    await state.update_data(amount=amount)
    await message.answer("توضیحات درخواست بازپرداخت را وارد کنید:")
    # Continue to next step
    await state.set_state(RefundRequestStates.waiting_description)


@router.message(RefundRequestStates.waiting_description)
async def refund_description(message: Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            # Create refund request
            refund_request = await RefundService.create_refund_request(
                session=session,
                user_id=user.id,
                service_id=data["service_id"],
                refund_type=RefundType(data["refund_type"]),
                refund_reason=RefundReason(data["refund_reason"]),
                requested_amount=data["amount"],
                description=description
            )
        
        await state.clear()
        
        reason_names = {
            "user_request": "درخواست کاربر",
            "service_issue": "مشکل سرویس",
            "technical_problem": "مشکل فنی",
            "billing_error": "خطای صورتحساب",
            "quality_issue": "مشکل کیفیت"
        }
        
        type_names = {
            "full_refund": "بازپرداخت کامل",
            "partial_refund": "بازپرداخت جزئی",
            "wallet_credit": "اعتبار کیف پول"
        }
        
        await message.answer(f"✅ درخواست بازپرداخت ثبت شد!\n\n"
                           f"شناسه درخواست: {refund_request.id}\n"
                           f"سرویس: {data['service_id']}\n"
                           f"نوع: {type_names.get(data['refund_type'], data['refund_type'])}\n"
                           f"دلیل: {reason_names.get(data['refund_reason'], data['refund_reason'])}\n"
                           f"مبلغ: {data['amount']:,.0f} تومان\n\n"
                           f"درخواست شما در حال بررسی است.")
        
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ خطا در ثبت درخواست: {str(e)}")


@router.message(Command("upgrade_service"))
async def upgrade_service_start(message: Message, state: FSMContext):
    """Start service upgrade process"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        # Get user's active services
        from models.service import Service
        services = (await session.execute(
            select(Service)
            .where(
                and_(
                    Service.user_id == user.id,
                    Service.is_active == True
                )
            )
        )).scalars().all()
        
        if not services:
            await message.answer("شما هیچ سرویس فعالی ندارید.")
            return
    
    # Show services for selection
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for service in services[:10]:  # Limit to 10 services
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"سرویس {service.id} - {service.remark or 'بدون توضیح'}",
                callback_data=f"upgrade_service:{service.id}"
            )
        ])
    
    await message.answer("سرویسی که می‌خواهید ارتقا دهید را انتخاب کنید:", reply_markup=kb)
    await state.set_state(UpgradeRequestStates.waiting_service)


@router.callback_query(F.data.startswith("upgrade_service:"))
async def upgrade_service_selected(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != UpgradeRequestStates.waiting_service:
        return
    
    service_id = int(callback.data.split(":")[1])
    await state.update_data(service_id=service_id)
    
    async with get_db_session() as session:
        from sqlalchemy import select
        from models.catalog import Plan
        
        # Get available plans
        plans = (await session.execute(
            select(Plan).where(Plan.is_active == True)
        )).scalars().all()
    
    # Show plans for selection
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for plan in plans[:10]:  # Limit to 10 plans
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{plan.title} - {plan.price_irr:,.0f} تومان",
                callback_data=f"upgrade_plan:{plan.id}"
            )
        ])
    
    await callback.message.edit_text("پلن جدید را انتخاب کنید:", reply_markup=kb)
    await state.set_state(UpgradeRequestStates.waiting_plan)
    await callback.answer()


@router.callback_query(F.data.startswith("upgrade_plan:"))
async def upgrade_plan_selected(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != UpgradeRequestStates.waiting_plan:
        return
    
    plan_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == callback.from_user.id)
            )).scalar_one()
            
            # Create upgrade request
            upgrade = await RefundService.create_service_upgrade(
                session=session,
                user_id=user.id,
                current_service_id=data["service_id"],
                target_plan_id=plan_id
            )
        
        await state.clear()
        
        await callback.message.edit_text(f"✅ درخواست ارتقای سرویس ثبت شد!\n\n"
                                       f"شناسه درخواست: {upgrade.id}\n"
                                       f"سرویس فعلی: {data['service_id']}\n"
                                       f"پلن جدید: {plan_id}\n"
                                       f"هزینه ارتقا: {upgrade.upgrade_cost:,.0f} تومان\n\n"
                                       f"درخواست شما در حال پردازش است.")
        
    except Exception as e:
        await state.clear()
        await callback.message.edit_text(f"❌ خطا در ثبت درخواست: {str(e)}")
    
    await callback.answer()


@router.message(Command("my_refunds"))
async def my_refunds(message: Message):
    """Show user's refund requests"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        from models.refund_system import RefundRequest
        refunds = (await session.execute(
            select(RefundRequest)
            .where(RefundRequest.user_id == user.id)
            .order_by(RefundRequest.created_at.desc())
            .limit(10)
        )).scalars().all()
    
    if not refunds:
        await message.answer("هیچ درخواست بازپرداختی ندارید.")
        return
    
    refunds_text = "💰 درخواست‌های بازپرداخت شما:\n\n"
    
    status_emojis = {
        RefundStatus.PENDING: "⏳",
        RefundStatus.APPROVED: "✅",
        RefundStatus.PROCESSING: "🔄",
        RefundStatus.COMPLETED: "✅",
        RefundStatus.REJECTED: "❌",
        RefundStatus.CANCELLED: "🚫"
    }
    
    type_emojis = {
        RefundType.FULL_REFUND: "💯",
        RefundType.PARTIAL_REFUND: "🔸",
        RefundType.WALLET_CREDIT: "💳",
        RefundType.SERVICE_CREDIT: "🎫",
        RefundType.UPGRADE_CREDIT: "⬆️"
    }
    
    for i, refund in enumerate(refunds, 1):
        status_emoji = status_emojis.get(refund.status, "❓")
        type_emoji = type_emojis.get(refund.refund_type, "❓")
        date_str = refund.created_at.strftime('%m/%d %H:%M')
        
        refunds_text += f"{i}. {status_emoji} {type_emoji} {refund.requested_amount:,.0f} تومان\n"
        refunds_text += f"   سرویس: {refund.service_id}\n"
        refunds_text += f"   وضعیت: {refund.status.value}\n"
        refunds_text += f"   تاریخ: {date_str}\n\n"
    
    await message.answer(refunds_text)


# Admin refund management
@router.message(Command("refund_requests"))
async def refund_requests(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, desc
        from models.refund_system import RefundRequest
        
        pending_refunds = (await session.execute(
            select(RefundRequest, TelegramUser)
            .join(TelegramUser, RefundRequest.user_id == TelegramUser.id)
            .where(RefundRequest.status == RefundStatus.PENDING)
            .order_by(desc(RefundRequest.created_at))
        )).all()
    
    if not pending_refunds:
        await message.answer("هیچ درخواست بازپرداخت در انتظار نیست.")
        return
    
    refunds_text = "💰 درخواست‌های بازپرداخت در انتظار:\n\n"
    
    for i, (refund, user) in enumerate(pending_refunds, 1):
        refunds_text += f"{i}. درخواست #{refund.id}\n"
        refunds_text += f"   کاربر: @{user.username or 'بدون نام کاربری'}\n"
        refunds_text += f"   سرویس: {refund.service_id}\n"
        refunds_text += f"   مبلغ: {refund.requested_amount:,.0f} تومان\n"
        refunds_text += f"   نوع: {refund.refund_type.value}\n"
        refunds_text += f"   دلیل: {refund.refund_reason.value}\n"
        refunds_text += f"   تاریخ: {refund.created_at.strftime('%Y/%m/%d')}\n\n"
    
    await message.answer(refunds_text)


@router.message(Command("approve_refund"))
async def approve_refund_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract refund ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /approve_refund <refund_id> [amount]")
        return
    
    try:
        refund_id = int(command_parts[1])
        approved_amount = float(command_parts[2]) if len(command_parts) > 2 else None
    except ValueError:
        await message.answer("شناسه بازپرداخت یا مبلغ نامعتبر است.")
        return
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            # Get refund request
            refund_request = (await session.execute(
                select(RefundRequest).where(RefundRequest.id == refund_id)
            )).scalar_one_or_none()
            
            if not refund_request:
                await message.answer("درخواست بازپرداخت یافت نشد.")
                return
            
            if approved_amount is None:
                approved_amount = refund_request.requested_amount
            
            # Approve refund
            await RefundService.approve_refund_request(
                session=session,
                refund_request_id=refund_id,
                approved_amount=approved_amount,
                processed_by=admin_user.id
            )
        
        await message.answer(f"✅ درخواست بازپرداخت #{refund_id} تایید شد!\n"
                           f"مبلغ تایید شده: {approved_amount:,.0f} تومان")
        
    except Exception as e:
        await message.answer(f"❌ خطا در تایید بازپرداخت: {str(e)}")


@router.message(Command("process_refunds"))
async def process_refunds(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            from models.refund_system import RefundRequest
            
            # Get approved refunds
            approved_refunds = (await session.execute(
                select(RefundRequest)
                .where(RefundRequest.status == RefundStatus.APPROVED)
            )).scalars().all()
            
            processed_count = 0
            for refund in approved_refunds:
                success = await RefundService.process_refund(session, refund.id)
                if success:
                    processed_count += 1
        
        await message.answer(f"✅ {processed_count} بازپرداخت پردازش شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش بازپرداخت‌ها: {str(e)}")


@router.message(Command("refund_analytics"))
async def refund_analytics(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract date range from command
    command_parts = message.text.split()
    if len(command_parts) < 3:
        await message.answer("فرمت: /refund_analytics <شروع> <پایان>\nمثال: /refund_analytics 2024-01-01 2024-01-31")
        return
    
    try:
        start_date = datetime.strptime(command_parts[1], "%Y-%m-%d")
        end_date = datetime.strptime(command_parts[2], "%Y-%m-%d")
    except ValueError:
        await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD استفاده کنید.")
        return
    
    try:
        async with get_db_session() as session:
            analytics = await RefundService.get_refund_analytics(session, start_date, end_date)
        
        analytics_text = f"""
📊 آمار بازپرداخت و ارتقا - {start_date.strftime('%Y/%m/%d')} تا {end_date.strftime('%Y/%m/%d')}

💰 بازپرداخت‌ها:
• کل درخواست‌ها: {analytics['refunds']['total_requests']}
• تایید شده: {analytics['refunds']['approved_count']}
• رد شده: {analytics['refunds']['rejected_count']}
• کل مبلغ: {analytics['refunds']['total_amount']:,.0f} تومان

⬆️ ارتقاها:
• کل درخواست‌ها: {analytics['upgrades']['total_requests']}
• تکمیل شده: {analytics['upgrades']['completed_count']}
• کل درآمد: {analytics['upgrades']['total_revenue']:,.0f} تومان
"""
        
        await message.answer(analytics_text)
        
    except Exception as e:
        await message.answer(f"❌ خطا در تولید آمار: {str(e)}")


@router.message(Command("refund_help"))
async def refund_help(message: Message):
    help_text = """
💰 راهنمای سیستم بازپرداخت و ارتقا:

👤 دستورات کاربری:
• /request_refund - درخواست بازپرداخت
• /upgrade_service - ارتقای سرویس
• /my_refunds - درخواست‌های بازپرداخت من

🔧 دستورات ادمین:
• /refund_requests - درخواست‌های بازپرداخت
• /approve_refund <id> [مبلغ] - تایید بازپرداخت
• /process_refunds - پردازش بازپرداخت‌ها
• /refund_analytics <شروع> <پایان> - آمار بازپرداخت

💰 انواع بازپرداخت:
• 💯 بازپرداخت کامل - بازپرداخت کامل و غیرفعال کردن سرویس
• 🔸 بازپرداخت جزئی - بازپرداخت بخشی از مبلغ
• 💳 اعتبار کیف پول - اضافه کردن مبلغ به کیف پول

📋 دلایل بازپرداخت:
• درخواست کاربر - درخواست شخصی کاربر
• مشکل سرویس - مشکل در سرویس
• مشکل فنی - مشکل فنی سیستم
• خطای صورتحساب - خطا در صورتحساب
• مشکل کیفیت - مشکل کیفیت سرویس

⬆️ ارتقای سرویس:
• ارتقای پلن - تغییر به پلن بهتر
• محاسبه هزینه بر اساس ارزش باقی‌مانده
• تخفیف‌های ویژه برای ارتقا
• پرداخت از کیف پول

📊 ویژگی‌ها:
• درخواست خودکار کاربران
• تایید دستی ادمین
• پردازش خودکار
• آمارگیری کامل
• مدیریت کیف پول
• قوانین بازپرداخت
"""
    
    await message.answer(help_text)