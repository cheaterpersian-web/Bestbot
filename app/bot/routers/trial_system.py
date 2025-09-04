from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.trial import TrialRequest, TrialConfig
from models.user import TelegramUser
from models.service import Service
from models.catalog import Server, Plan
from services.purchases import create_service_after_payment


router = Router(name="trial_system")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class TrialRequestStates(StatesGroup):
    waiting_duration = State()
    waiting_traffic = State()
    waiting_reason = State()


# User-side trial request
@router.message(Command("request_trial"))
async def request_trial_start(message: Message, state: FSMContext):
    async with get_db_session() as session:
        from sqlalchemy import select
        
        # Check if trial system is enabled
        trial_config = (await session.execute(
            select(TrialConfig).where(TrialConfig.id == 1)
        )).scalar_one_or_none()
        
        if not trial_config or not trial_config.is_enabled:
            await message.answer("سیستم تست رایگان در حال حاضر غیرفعال است.")
            return
        
        # Check if user already has a pending or approved request
        existing_request = (await session.execute(
            select(TrialRequest)
            .where(TrialRequest.user_id == message.from_user.id)
            .where(TrialRequest.status.in_(["pending", "approved"]))
        )).scalar_one_or_none()
        
        if existing_request:
            status_text = {
                "pending": "در انتظار بررسی",
                "approved": "تایید شده"
            }.get(existing_request.status, "نامشخص")
            await message.answer(f"شما قبلاً درخواست تست داده‌اید.\nوضعیت: {status_text}")
            return
        
        # Check daily request limit
        today = datetime.utcnow().date()
        daily_requests = (await session.execute(
            select(TrialRequest)
            .where(TrialRequest.created_at >= today)
        )).scalars().all()
        
        if len(daily_requests) >= trial_config.max_requests_per_day:
            await message.answer("حد مجاز درخواست‌های روزانه به پایان رسیده است. لطفاً فردا تلاش کنید.")
            return
        
        # Check user request limit
        user_requests = (await session.execute(
            select(TrialRequest)
            .where(TrialRequest.user_id == message.from_user.id)
        )).scalars().all()
        
        if len(user_requests) >= trial_config.max_requests_per_user:
            await message.answer("شما به حد مجاز درخواست‌های تست رسیده‌اید.")
            return
    
    await message.answer(f"مدت زمان تست مورد نظر خود را انتخاب کنید (حداکثر {trial_config.max_duration_days} روز):")
    await state.set_state(TrialRequestStates.waiting_duration)


@router.message(TrialRequestStates.waiting_duration)
async def trial_duration(message: Message, state: FSMContext):
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            await message.answer("مدت زمان باید مثبت باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        trial_config = (await session.execute(
            select(TrialConfig).where(TrialConfig.id == 1)
        )).scalar_one_or_none()
        
        if duration > trial_config.max_duration_days:
            await message.answer(f"حداکثر مدت زمان تست {trial_config.max_duration_days} روز است.")
            return
    
    await state.update_data(duration=duration)
    
    if trial_config.max_traffic_gb:
        await message.answer(f"حجم ترافیک مورد نظر خود را وارد کنید (حداکثر {trial_config.max_traffic_gb} گیگابایت):")
        await state.set_state(TrialRequestStates.waiting_traffic)
    else:
        await state.update_data(traffic=None)
        await message.answer("دلیل درخواست تست را شرح دهید:")
        await state.set_state(TrialRequestStates.waiting_reason)


@router.message(TrialRequestStates.waiting_traffic)
async def trial_traffic(message: Message, state: FSMContext):
    try:
        traffic = float(message.text.strip())
        if traffic <= 0:
            await message.answer("حجم ترافیک باید مثبت باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        trial_config = (await session.execute(
            select(TrialConfig).where(TrialConfig.id == 1)
        )).scalar_one_or_none()
        
        if trial_config.max_traffic_gb and traffic > trial_config.max_traffic_gb:
            await message.answer(f"حداکثر حجم ترافیک {trial_config.max_traffic_gb} گیگابایت است.")
            return
    
    await state.update_data(traffic=traffic)
    await message.answer("دلیل درخواست تست را شرح دهید:")
    await state.set_state(TrialRequestStates.waiting_reason)


@router.message(TrialRequestStates.waiting_reason)
async def trial_reason(message: Message, state: FSMContext):
    reason = message.text.strip()
    data = await state.get_data()
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        trial_config = (await session.execute(
            select(TrialConfig).where(TrialConfig.id == 1)
        )).scalar_one()
        
        # Create trial request
        trial_request = TrialRequest(
            user_id=user.id,
            requested_duration_days=data["duration"],
            requested_traffic_gb=data.get("traffic"),
            reason=reason,
            status="pending"
        )
        
        # Auto-approve if enabled
        if trial_config.auto_approve:
            trial_request.status = "approved"
            trial_request.approved_duration_days = data["duration"]
            trial_request.approved_traffic_gb = data.get("traffic")
            trial_request.reviewed_at = datetime.utcnow()
            trial_request.expires_at = datetime.utcnow() + timedelta(days=data["duration"])
            
            # Create trial service
            await _create_trial_service(session, trial_request, trial_config)
        
        session.add(trial_request)
    
    await state.clear()
    
    if trial_config.auto_approve:
        await message.answer("✅ درخواست تست شما تایید شد!\nسرویس تست شما ایجاد شده و به‌زودی فعال خواهد شد.")
    else:
        await message.answer("✅ درخواست تست شما ثبت شد.\nادمین‌ها به‌زودی درخواست شما را بررسی خواهند کرد.")


async def _create_trial_service(session, trial_request: TrialRequest, trial_config: TrialConfig):
    """Create a trial service for approved request"""
    from sqlalchemy import select
    from services.panels.factory import PanelFactory
    
    # Get default server and plan
    server = None
    plan = None
    
    if trial_config.server_id:
        server = (await session.execute(
            select(Server).where(Server.id == trial_config.server_id)
        )).scalar_one_or_none()
    
    if trial_config.plan_id:
        plan = (await session.execute(
            select(Plan).where(Plan.id == trial_config.plan_id)
        )).scalar_one_or_none()
    
    if not server:
        server = (await session.execute(
            select(Server).where(Server.is_active == True).order_by(Server.id)
        )).scalar_one_or_none()
    
    if not server:
        return  # No active server available
    
    # Create a temporary plan for trial
    if not plan:
        plan = Plan(
            title=f"تست {trial_request.approved_duration_days} روزه",
            price_irr=0,
            duration_days=trial_request.approved_duration_days,
            traffic_gb=trial_request.approved_traffic_gb,
            is_active=True
        )
        session.add(plan)
        await session.flush()
    
    # Create service using panel
    try:
        panel = PanelFactory.create_panel(server.panel_type, server.api_base_url, server.api_key)
        
        service_data = await panel.create_service(
            remark=f"Trial-{trial_request.user_id}",
            traffic_gb=trial_request.approved_traffic_gb,
            duration_days=trial_request.approved_duration_days
        )
        
        if service_data:
            service = Service(
                user_id=trial_request.user_id,
                server_id=server.id,
                plan_id=plan.id,
                remark=service_data["remark"],
                uuid=service_data["uuid"],
                subscription_url=service_data["subscription_url"],
                is_active=True,
                is_test=True,
                expires_at=trial_request.expires_at,
                traffic_limit_gb=trial_request.approved_traffic_gb
            )
            session.add(service)
            await session.flush()
            
            trial_request.service_id = service.id
            
    except Exception as e:
        # Log error but don't fail the request
        print(f"Error creating trial service: {e}")


# Admin-side trial management
@router.message(Command("list_trial_requests"))
async def list_trial_requests(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        requests = (await session.execute(
            select(TrialRequest)
            .where(TrialRequest.status == "pending")
            .order_by(TrialRequest.created_at.desc())
        )).scalars().all()
    
    if not requests:
        await message.answer("درخواست تست در انتظار بررسی وجود ندارد.")
        return
    
    out = []
    for req in requests:
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == req.user_id)
        )).scalar_one()
        
        out.append(f"🆔 {req.id} - @{user.username or 'بدون نام کاربری'}\n"
                  f"مدت: {req.requested_duration_days} روز\n"
                  f"ترافیک: {req.requested_traffic_gb or 'نامحدود'} گیگ\n"
                  f"تاریخ: {req.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    await message.answer("\n\n".join(out))


@router.message(Command("trial_requests"))
async def trial_requests_menu(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        requests = (await session.execute(
            select(TrialRequest)
            .where(TrialRequest.status == "pending")
            .order_by(TrialRequest.created_at.desc())
            .limit(10)
        )).scalars().all()
    
    if not requests:
        await message.answer("درخواست تست در انتظار بررسی وجود ندارد.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🆔 {req.id} - {req.requested_duration_days}روز", 
                            callback_data=f"trial_request:{req.id}")]
        for req in requests
    ])
    
    await message.answer("درخواست تست را برای بررسی انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("trial_request:"))
async def trial_request_details(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(TrialRequest).where(TrialRequest.id == request_id)
        )).scalar_one_or_none()
        
        if not request:
            await callback.answer("درخواست یافت نشد")
            return
        
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == request.user_id)
        )).scalar_one()
        
        text = f"📋 درخواست تست #{request.id}\n\n"
        text += f"👤 کاربر: @{user.username or 'بدون نام کاربری'} ({user.telegram_user_id})\n"
        text += f"📅 تاریخ: {request.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        text += f"⏰ مدت درخواستی: {request.requested_duration_days} روز\n"
        text += f"📊 ترافیک درخواستی: {request.requested_traffic_gb or 'نامحدود'} گیگ\n\n"
        text += f"📝 دلیل:\n{request.reason}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید", callback_data=f"approve_trial:{request_id}"),
             InlineKeyboardButton(text="❌ رد", callback_data=f"reject_trial:{request_id}")]
        ])
        
        await callback.message.answer(text, reply_markup=kb)
        await callback.answer()


@router.callback_query(F.data.startswith("approve_trial:"))
async def approve_trial(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(TrialRequest).where(TrialRequest.id == request_id)
        )).scalar_one_or_none()
        
        if not request:
            await callback.answer("درخواست یافت نشد")
            return
        
        if request.status != "pending":
            await callback.answer("این درخواست قبلاً بررسی شده است")
            return
        
        # Update request status
        request.status = "approved"
        request.approved_duration_days = request.requested_duration_days
        request.approved_traffic_gb = request.requested_traffic_gb
        request.reviewed_by_admin_id = callback.from_user.id
        request.reviewed_at = datetime.utcnow()
        request.expires_at = datetime.utcnow() + timedelta(days=request.approved_duration_days)
        
        # Get trial config
        trial_config = (await session.execute(
            select(TrialConfig).where(TrialConfig.id == 1)
        )).scalar_one()
        
        # Create trial service
        await _create_trial_service(session, request, trial_config)
        
        # Notify user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == request.user_id)
        )).scalar_one()
        
        try:
            from aiogram import Bot
            bot = Bot(token=settings.bot_token)
            await bot.send_message(
                user.telegram_user_id,
                f"🎉 درخواست تست شما تایید شد!\n"
                f"مدت: {request.approved_duration_days} روز\n"
                f"ترافیک: {request.approved_traffic_gb or 'نامحدود'} گیگ\n"
                f"سرویس تست شما به‌زودی فعال خواهد شد."
            )
        except Exception:
            pass  # User might have blocked the bot
    
    await callback.answer("درخواست تایید شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("reject_trial:"))
async def reject_trial(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(TrialRequest).where(TrialRequest.id == request_id)
        )).scalar_one_or_none()
        
        if not request:
            await callback.answer("درخواست یافت نشد")
            return
        
        if request.status != "pending":
            await callback.answer("این درخواست قبلاً بررسی شده است")
            return
        
        # Update request status
        request.status = "rejected"
        request.reviewed_by_admin_id = callback.from_user.id
        request.reviewed_at = datetime.utcnow()
        
        # Notify user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == request.user_id)
        )).scalar_one()
        
        try:
            from aiogram import Bot
            bot = Bot(token=settings.bot_token)
            await bot.send_message(
                user.telegram_user_id,
                "متاسفانه درخواست تست شما رد شد.\n"
                "در صورت تمایل می‌توانید مجدداً درخواست دهید."
            )
        except Exception:
            pass  # User might have blocked the bot
    
    await callback.answer("درخواست رد شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(Command("trial_config"))
async def trial_config(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        config = (await session.execute(
            select(TrialConfig).where(TrialConfig.id == 1)
        )).scalar_one_or_none()
        
        if not config:
            # Create default config
            config = TrialConfig(id=1)
            session.add(config)
            await session.flush()
        
        text = "⚙️ تنظیمات سیستم تست\n\n"
        text += f"فعال: {'✅' if config.is_enabled else '❌'}\n"
        text += f"حداکثر مدت: {config.max_duration_days} روز\n"
        text += f"حداکثر ترافیک: {config.max_traffic_gb or 'نامحدود'} گیگ\n"
        text += f"حد درخواست کاربر: {config.max_requests_per_user}\n"
        text += f"حد درخواست روزانه: {config.max_requests_per_day}\n"
        text += f"تایید خودکار: {'✅' if config.auto_approve else '❌'}\n"
        text += f"نیاز به تایید تلفن: {'✅' if config.require_phone_verification else '❌'}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔧 ویرایش تنظیمات", callback_data="edit_trial_config")]
        ])
        
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "edit_trial_config")
async def edit_trial_config(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    # This would open a configuration interface
    # For now, just show current settings
    await callback.answer("ویرایش تنظیمات - در حال توسعه")