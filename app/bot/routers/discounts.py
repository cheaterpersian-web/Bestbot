from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.discounts import DiscountCode
from models.user import TelegramUser
from bot.inline import discount_code_actions_kb


router = Router(name="discounts")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class AddDiscountStates(StatesGroup):
    waiting_code = State()
    waiting_title = State()
    waiting_type = State()
    waiting_value = State()
    waiting_usage_limit = State()
    waiting_valid_from = State()
    waiting_valid_to = State()
    waiting_applications = State()


@router.message(Command("add_discount"))
async def add_discount_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    await message.answer("کد تخفیف را وارد کنید (مثال: WELCOME20)")
    await state.set_state(AddDiscountStates.waiting_code)


@router.message(AddDiscountStates.waiting_code)
async def add_discount_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    async with get_db_session() as session:
        from sqlalchemy import select
        existing = (await session.execute(select(DiscountCode).where(DiscountCode.code == code))).scalar_one_or_none()
        if existing:
            await message.answer("این کد قبلاً استفاده شده است. کد دیگری انتخاب کنید.")
            return
    await state.update_data(code=code)
    await message.answer("عنوان کد تخفیف را وارد کنید (مثال: تخفیف خوش آمدگویی)")
    await state.set_state(AddDiscountStates.waiting_title)


@router.message(AddDiscountStates.waiting_title)
async def add_discount_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("نوع تخفیف را انتخاب کنید:\n1. percent - درصدی (مثال: 20%)\n2. fixed - مبلغ ثابت (مثال: 50000 تومان)")
    await state.set_state(AddDiscountStates.waiting_type)


@router.message(AddDiscountStates.waiting_type)
async def add_discount_type(message: Message, state: FSMContext):
    discount_type = message.text.strip().lower()
    if discount_type not in ["percent", "fixed", "1", "2"]:
        await message.answer("نوع نامعتبر است. یکی از percent یا fixed انتخاب کنید.")
        return
    
    # Convert numbers to types
    type_map = {"1": "percent", "2": "fixed"}
    discount_type = type_map.get(discount_type, discount_type)
    
    await state.update_data(type=discount_type)
    
    if discount_type == "percent":
        await message.answer("درصد تخفیف را وارد کنید (مثال: 20)")
    else:
        await message.answer("مبلغ تخفیف را وارد کنید (تومان)")
    
    await state.set_state(AddDiscountStates.waiting_value)


@router.message(AddDiscountStates.waiting_value)
async def add_discount_value(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if value <= 0:
            await message.answer("مقدار باید مثبت باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    if data["type"] == "percent" and value > 100:
        await message.answer("درصد تخفیف نمی‌تواند بیشتر از 100 باشد.")
        return
    
    await state.update_data(value=value)
    await message.answer("حداکثر تعداد استفاده (0 برای نامحدود):")
    await state.set_state(AddDiscountStates.waiting_usage_limit)


@router.message(AddDiscountStates.waiting_usage_limit)
async def add_discount_usage_limit(message: Message, state: FSMContext):
    try:
        limit = int(message.text.strip())
        if limit < 0:
            await message.answer("تعداد استفاده نمی‌تواند منفی باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    await state.update_data(usage_limit=limit if limit > 0 else None)
    await message.answer("تاریخ شروع اعتبار (YYYY-MM-DD یا 'now' برای الان):")
    await state.set_state(AddDiscountStates.waiting_valid_from)


@router.message(AddDiscountStates.waiting_valid_from)
async def add_discount_valid_from(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text == "now":
        valid_from = datetime.utcnow()
    else:
        try:
            valid_from = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD استفاده کنید.")
            return
    
    await state.update_data(valid_from=valid_from)
    await message.answer("تاریخ پایان اعتبار (YYYY-MM-DD یا 'never' برای نامحدود):")
    await state.set_state(AddDiscountStates.waiting_valid_to)


@router.message(AddDiscountStates.waiting_valid_to)
async def add_discount_valid_to(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text == "never":
        valid_to = None
    else:
        try:
            valid_to = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD استفاده کنید.")
            return
    
    await state.update_data(valid_to=valid_to)
    await message.answer("کد تخفیف روی چه مواردی اعمال شود؟\n1. خرید\n2. تمدید\n3. شارژ کیف پول\n4. همه موارد\n\nعدد مربوطه را وارد کنید (مثال: 1,2,3):")
    await state.set_state(AddDiscountStates.waiting_applications)


@router.message(AddDiscountStates.waiting_applications)
async def add_discount_applications(message: Message, state: FSMContext):
    text = message.text.strip()
    applications = []
    
    if "1" in text:
        applications.append("purchase")
    if "2" in text:
        applications.append("renewal")
    if "3" in text:
        applications.append("wallet")
    if "4" in text:
        applications = ["purchase", "renewal", "wallet"]
    
    if not applications:
        await message.answer("حداقل یک مورد را انتخاب کنید.")
        return
    
    data = await state.get_data()
    
    async with get_db_session() as session:
        discount = DiscountCode(
            code=data["code"],
            title=data["title"],
            percent_off=data["value"] if data["type"] == "percent" else 0,
            fixed_off=data["value"] if data["type"] == "fixed" else 0,
            usage_limit=data["usage_limit"],
            valid_from=data["valid_from"],
            valid_to=data["valid_to"],
            apply_on_purchase="purchase" in applications,
            apply_on_renewal="renewal" in applications,
            apply_on_wallet="wallet" in applications,
            active=True
        )
        session.add(discount)
    
    await state.clear()
    await message.answer("کد تخفیف با موفقیت اضافه شد.")


@router.message(Command("list_discounts"))
async def list_discounts(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discounts = (await session.execute(select(DiscountCode).order_by(DiscountCode.created_at.desc()))).scalars().all()
    
    if not discounts:
        await message.answer("کد تخفیفی ثبت نشده است.")
        return
    
    out = []
    for d in discounts:
        status = "✅" if d.active else "❌"
        discount_type = f"{d.percent_off}%" if d.percent_off > 0 else f"{d.fixed_off:,} تومان"
        usage_info = f"{d.used_count}/{d.usage_limit or '∞'}"
        
        applications = []
        if d.apply_on_purchase:
            applications.append("خرید")
        if d.apply_on_renewal:
            applications.append("تمدید")
        if d.apply_on_wallet:
            applications.append("کیف پول")
        
        valid_info = "همیشه" if not d.valid_to else d.valid_to.strftime("%Y-%m-%d")
        
        out.append(f"{status} {d.code} - {d.title}\n   تخفیف: {discount_type}\n   استفاده: {usage_info}\n   اعمال: {', '.join(applications)}\n   اعتبار تا: {valid_info}")
    
    await message.answer("\n\n".join(out))


@router.message(Command("discount_stats"))
async def discount_stats_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discounts = (await session.execute(select(DiscountCode).order_by(DiscountCode.created_at.desc()))).scalars().all()
    
    if not discounts:
        await message.answer("کد تخفیفی ثبت نشده است.")
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📊 {d.code}", callback_data=f"discount_stats:{d.id}")]
        for d in discounts
    ])
    
    await message.answer("کد تخفیفی را برای مشاهده آمار انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("discount_stats:"))
async def discount_stats_callback(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    discount_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        discount = (await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id))).scalar_one_or_none()
        if not discount:
            await callback.answer("کد تخفیف یافت نشد")
            return
        
        # Get usage statistics
        from models.billing import Transaction
        usage_count = (await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.discount_code == discount.code)
        )).scalar()
        
        total_savings = (await session.execute(
            select(func.sum(Transaction.bonus_amount))
            .where(Transaction.discount_code == discount.code)
        )).scalar() or 0
    
    text = f"📊 آمار کد تخفیف: {discount.code}\n\n"
    text += f"عنوان: {discount.title}\n"
    text += f"تخفیف: {discount.percent_off}% / {discount.fixed_off:,} تومان\n"
    text += f"تعداد استفاده: {usage_count}\n"
    text += f"حداکثر استفاده: {discount.usage_limit or 'نامحدود'}\n"
    text += f"کل صرفه‌جویی: {total_savings:,.0f} تومان\n"
    text += f"وضعیت: {'فعال' if discount.active else 'غیرفعال'}\n"
    
    if discount.valid_to:
        text += f"اعتبار تا: {discount.valid_to.strftime('%Y-%m-%d')}\n"
    
    await callback.message.answer(text)
    await callback.answer()


@router.message(Command("toggle_discount"))
async def toggle_discount_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discounts = (await session.execute(select(DiscountCode).order_by(DiscountCode.created_at.desc()))).scalars().all()
    
    if not discounts:
        await message.answer("کد تخفیفی ثبت نشده است.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'✅' if d.active else '❌'} {d.code}", callback_data=f"toggle_discount:{d.id}")]
        for d in discounts
    ])
    
    await message.answer("کد تخفیفی را برای تغییر وضعیت انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("toggle_discount:"))
async def toggle_discount_callback(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    discount_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discount = (await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id))).scalar_one_or_none()
        if not discount:
            await callback.answer("کد تخفیف یافت نشد")
            return
        
        discount.active = not discount.active
    
    await callback.answer(f"وضعیت کد تخفیف {'فعال' if discount.active else 'غیرفعال'} شد")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(Command("delete_discount"))
async def delete_discount_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discounts = (await session.execute(select(DiscountCode).order_by(DiscountCode.created_at.desc()))).scalars().all()
    
    if not discounts:
        await message.answer("کد تخفیفی ثبت نشده است.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑️ {d.code}", callback_data=f"delete_discount:{d.id}")]
        for d in discounts
    ])
    
    await message.answer("کد تخفیفی را برای حذف انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data.startswith("delete_discount:"))
async def delete_discount_callback(callback: CallbackQuery):
    if not await _is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید")
        return
    
    discount_id = int(callback.data.split(":")[1])
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discount = (await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id))).scalar_one_or_none()
        if not discount:
            await callback.answer("کد تخفیف یافت نشد")
            return
        
        await session.delete(discount)
    
    await callback.answer("کد تخفیف حذف شد")
    await callback.message.edit_reply_markup(reply_markup=None)


# User-side discount code application
@router.message(Command("apply_discount"))
async def apply_discount_start(message: Message, state: FSMContext):
    await message.answer("کد تخفیف خود را وارد کنید:")
    await state.set_state("waiting_discount_code")


@router.message(F.text.regexp(r'^[A-Z0-9]+$'))
async def apply_discount_code(message: Message, state: FSMContext):
    if await state.get_state() != "waiting_discount_code":
        return
    
    code = message.text.strip().upper()
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discount = (await session.execute(select(DiscountCode).where(DiscountCode.code == code))).scalar_one_or_none()
        
        if not discount:
            await message.answer("کد تخفیف نامعتبر است.")
            await state.clear()
            return
        
        if not discount.active:
            await message.answer("این کد تخفیف غیرفعال است.")
            await state.clear()
            return
        
        now = datetime.utcnow()
        if discount.valid_from and now < discount.valid_from:
            await message.answer("این کد تخفیف هنوز فعال نشده است.")
            await state.clear()
            return
        
        if discount.valid_to and now > discount.valid_to:
            await message.answer("این کد تخفیف منقضی شده است.")
            await state.clear()
            return
        
        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            await message.answer("این کد تخفیف به حد استفاده رسیده است.")
            await state.clear()
            return
        
        # Store discount code in user's session for next purchase
        await state.update_data(selected_discount_code=code)
        await state.clear()
        
        discount_type = f"{discount.percent_off}%" if discount.percent_off > 0 else f"{discount.fixed_off:,} تومان"
        await message.answer(f"✅ کد تخفیف {code} با موفقیت اعمال شد!\nتخفیف: {discount_type}\nاین تخفیف در خرید بعدی شما اعمال خواهد شد.")