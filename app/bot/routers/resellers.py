from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.admin import ResellerRequest, Reseller
from models.user import TelegramUser
from bot.inline import reseller_request_actions_kb


router = Router(name="resellers")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class ResellerRequestStates(StatesGroup):
    waiting_business_info = State()
    waiting_contact_info = State()
    waiting_discount_request = State()


# User-side reseller request
@router.message(Command("request_reseller"))
async def request_reseller_start(message: Message, state: FSMContext):
    async with get_db_session() as session:
        from sqlalchemy import select
        # Check if user already has a pending or approved request
        existing_request = (await session.execute(
            select(ResellerRequest)
            .where(ResellerRequest.user_id == message.from_user.id)
        )).scalar_one_or_none()
        
        if existing_request:
            status_text = {
                "pending": "در انتظار بررسی",
                "approved": "تایید شده",
                "rejected": "رد شده",
                "blacklisted": "در لیست سیاه"
            }.get(existing_request.status, "نامشخص")
            await message.answer(f"شما قبلاً درخواست نمایندگی داده‌اید.\nوضعیت: {status_text}")
            return
        
        # Check if user is already a reseller
        existing_reseller = (await session.execute(
            select(Reseller)
            .where(Reseller.user_id == message.from_user.id)
        )).scalar_one_or_none()
        
        if existing_reseller:
            await message.answer("شما قبلاً نماینده هستید.")
            return
    
    await message.answer("اطلاعات کسب‌وکار خود را شرح دهید:")
    await state.set_state(ResellerRequestStates.waiting_business_info)


@router.message(ResellerRequestStates.waiting_business_info)
async def reseller_business_info(message: Message, state: FSMContext):
    await state.update_data(business_info=message.text.strip())
    await message.answer("اطلاعات تماس خود را وارد کنید (شماره تلفن، تلگرام، ایمیل و...):")
    await state.set_state(ResellerRequestStates.waiting_contact_info)


@router.message(ResellerRequestStates.waiting_contact_info)
async def reseller_contact_info(message: Message, state: FSMContext):
    await state.update_data(contact_info=message.text.strip())
    await message.answer("درصد تخفیف درخواستی خود را وارد کنید (0-50):")
    await state.set_state(ResellerRequestStates.waiting_discount_request)


@router.message(ResellerRequestStates.waiting_discount_request)
async def reseller_discount_request(message: Message, state: FSMContext):
    try:
        discount_percent = int(message.text.strip())
        if discount_percent < 0 or discount_percent > 50:
            await message.answer("درصد تخفیف باید بین 0 تا 50 باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        request = ResellerRequest(
            user_id=user.id,
            business_info=data["business_info"],
            contact_info=data["contact_info"],
            requested_discount_percent=discount_percent,
            status="pending"
        )
        session.add(request)
    
    await state.clear()
    await message.answer("✅ درخواست نمایندگی شما ثبت شد.\nادمین‌ها به‌زودی درخواست شما را بررسی خواهند کرد.")


# Admin-side reseller management
@router.message(Command("list_reseller_requests"))
async def list_reseller_requests(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        requests = (await session.execute(
            select(ResellerRequest)
            .where(ResellerRequest.status == "pending")
            .order_by(ResellerRequest.created_at.desc())
        )).scalars().all()
    
    if not requests:
        await message.answer("درخواست نمایندگی در انتظار بررسی وجود ندارد.")
        return
    
    out = []
    for req in requests:
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == req.user_id)
        )).scalar_one()
        
        out.append(f"🆔 {req.id} - @{user.username or 'بدون نام کاربری'}\n"
                  f"درخواست تخفیف: {req.requested_discount_percent}%\n"
                  f"تاریخ: {req.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    await message.answer("\n\n".join(out))


@router.message(Command("reseller_requests"))
async def reseller_requests_menu(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        requests = (await session.execute(
            select(ResellerRequest)
            .where(ResellerRequest.status == "pending")
            .order_by(ResellerRequest.created_at.desc())
            .limit(10)
        )).scalars().all()
    
    if not requests:
        await message.answer("درخواست نمایندگی در انتظار بررسی وجود ندارد.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🆔 {req.id} - {req.requested_discount_percent}%", 
                            callback_data=f"reseller_request:{req.id}")]
        for req in requests
    ])
    
    await message.answer("درخواست نمایندگی را برای بررسی انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("reseller_request:"))
async def reseller_request_details(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(ResellerRequest).where(ResellerRequest.id == request_id)
        )).scalar_one_or_none()
        
        if not request:
            await callback.answer("درخواست یافت نشد")
            return
        
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == request.user_id)
        )).scalar_one()
        
        text = f"📋 درخواست نمایندگی #{request.id}\n\n"
        text += f"👤 کاربر: @{user.username or 'بدون نام کاربری'} ({user.telegram_user_id})\n"
        text += f"📅 تاریخ: {request.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        text += f"💰 درخواست تخفیف: {request.requested_discount_percent}%\n\n"
        text += f"🏢 اطلاعات کسب‌وکار:\n{request.business_info}\n\n"
        text += f"📞 اطلاعات تماس:\n{request.contact_info}"
        
        kb = reseller_request_actions_kb(request_id)
        await callback.message.answer(text, reply_markup=kb)
        await callback.answer()


@router.callback_query(F.data.startswith("admin:approve_reseller:"))
async def approve_reseller(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[2])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(ResellerRequest).where(ResellerRequest.id == request_id)
        )).scalar_one_or_none()
        
        if not request:
            await callback.answer("درخواست یافت نشد")
            return
        
        if request.status != "pending":
            await callback.answer("این درخواست قبلاً بررسی شده است")
            return
        
        # Update request status
        request.status = "approved"
        request.reviewed_by_admin_id = callback.from_user.id
        request.reviewed_at = datetime.utcnow()
        request.approved_discount_percent = request.requested_discount_percent
        
        # Create reseller record
        reseller = Reseller(
            user_id=request.user_id,
            discount_percent=request.approved_discount_percent,
            is_active=True
        )
        session.add(reseller)
        
        # Notify user
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == request.user_id)
        )).scalar_one()
        
        try:
            from aiogram import Bot
            bot = Bot(token=settings.bot_token)
            await bot.send_message(
                user.telegram_user_id,
                f"🎉 تبریک! درخواست نمایندگی شما تایید شد.\n"
                f"درصد تخفیف شما: {request.approved_discount_percent}%\n"
                f"شما می‌توانید از این پس از تخفیف نمایندگی استفاده کنید."
            )
        except Exception:
            pass  # User might have blocked the bot
    
    await callback.answer("درخواست تایید شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:reject_reseller:"))
async def reject_reseller(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[2])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(ResellerRequest).where(ResellerRequest.id == request_id)
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
                "متاسفانه درخواست نمایندگی شما رد شد.\n"
                "در صورت تمایل می‌توانید مجدداً درخواست دهید."
            )
        except Exception:
            pass  # User might have blocked the bot
    
    await callback.answer("درخواست رد شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:blacklist_reseller:"))
async def blacklist_reseller(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    request_id = int(callback.data.split(":")[2])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        request = (await session.execute(
            select(ResellerRequest).where(ResellerRequest.id == request_id)
        )).scalar_one_or_none()
        
        if not request:
            await callback.answer("درخواست یافت نشد")
            return
        
        if request.status != "pending":
            await callback.answer("این درخواست قبلاً بررسی شده است")
            return
        
        # Update request status
        request.status = "blacklisted"
        request.reviewed_by_admin_id = callback.from_user.id
        request.reviewed_at = datetime.utcnow()
    
    await callback.answer("کاربر در لیست سیاه قرار گرفت")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(Command("list_resellers"))
async def list_resellers(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        resellers = (await session.execute(
            select(Reseller)
            .where(Reseller.is_active == True)
            .order_by(Reseller.created_at.desc())
        )).scalars().all()
    
    if not resellers:
        await message.answer("نماینده فعالی وجود ندارد.")
        return
    
    out = []
    for reseller in resellers:
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == reseller.user_id)
        )).scalar_one()
        
        status = "✅" if reseller.is_active else "❌"
        out.append(f"{status} @{user.username or 'بدون نام کاربری'}\n"
                  f"تخفیف: {reseller.discount_percent}%\n"
                  f"فروش کل: {reseller.total_sales:,.0f} تومان\n"
                  f"کمیسیون: {reseller.total_commission:,.0f} تومان")
    
    await message.answer("\n\n".join(out))


@router.message(Command("reseller_stats"))
async def reseller_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        
        # Total resellers
        total_resellers = (await session.execute(
            select(func.count(Reseller.id))
        )).scalar()
        
        # Active resellers
        active_resellers = (await session.execute(
            select(func.count(Reseller.id))
            .where(Reseller.is_active == True)
        )).scalar()
        
        # Total sales by resellers
        total_sales = (await session.execute(
            select(func.sum(Reseller.total_sales))
        )).scalar() or 0
        
        # Total commission paid
        total_commission = (await session.execute(
            select(func.sum(Reseller.total_commission))
        )).scalar() or 0
        
        # Pending requests
        pending_requests = (await session.execute(
            select(func.count(ResellerRequest.id))
            .where(ResellerRequest.status == "pending")
        )).scalar()
    
    text = "📊 آمار نمایندگان\n\n"
    text += f"👥 کل نمایندگان: {total_resellers}\n"
    text += f"✅ نمایندگان فعال: {active_resellers}\n"
    text += f"⏳ درخواست‌های در انتظار: {pending_requests}\n"
    text += f"💰 کل فروش نمایندگان: {total_sales:,.0f} تومان\n"
    text += f"💸 کل کمیسیون پرداختی: {total_commission:,.0f} تومان"
    
    await message.answer(text)


@router.message(Command("toggle_reseller"))
async def toggle_reseller_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        resellers = (await session.execute(
            select(Reseller)
            .order_by(Reseller.created_at.desc())
        )).scalars().all()
    
    if not resellers:
        await message.answer("نماینده‌ای ثبت نشده است.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'✅' if r.is_active else '❌'} {r.discount_percent}%", 
                            callback_data=f"toggle_reseller:{r.id}")]
        for r in resellers
    ])
    
    await message.answer("نماینده‌ای را برای تغییر وضعیت انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("toggle_reseller:"))
async def toggle_reseller_callback(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    reseller_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        reseller = (await session.execute(
            select(Reseller).where(Reseller.id == reseller_id)
        )).scalar_one_or_none()
        
        if not reseller:
            await callback.answer("نماینده یافت نشد")
            return
        
        reseller.is_active = not reseller.is_active
    
    await callback.answer(f"وضعیت نماینده {'فعال' if reseller.is_active else 'غیرفعال'} شد")
    await callback.message.edit_reply_markup(reply_markup=None)