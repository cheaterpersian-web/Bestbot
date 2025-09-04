import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.smart_discounts import SmartDiscount, CashbackRule, DiscountType
from models.user import TelegramUser
from services.smart_discount_service import SmartDiscountService


router = Router(name="smart_discounts")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class AddSmartDiscountStates(StatesGroup):
    waiting_name = State()
    waiting_type = State()
    waiting_discount_value = State()
    waiting_conditions = State()
    waiting_limits = State()
    waiting_targets = State()


# Admin Smart Discount Management
@router.message(Command("add_smart_discount"))
async def add_smart_discount_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    await message.answer("نام تخفیف هوشمند را وارد کنید:")
    await state.set_state(AddSmartDiscountStates.waiting_name)


@router.message(AddSmartDiscountStates.waiting_name)
async def add_smart_discount_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    
    types_text = """
نوع تخفیف را انتخاب کنید:

1️⃣ ساعتی - تخفیف در ساعات خاص
2️⃣ خرید اول - تخفیف برای خرید اول
3️⃣ کش‌بک - بازگشت پول
4️⃣ خرید عمده - تخفیف برای خریدهای بزرگ
5️⃣ وفاداری - تخفیف بر اساس سطح وفاداری
6️⃣ فصلی - تخفیف‌های فصلی
7️⃣ تولد - تخفیف تولد

عدد مربوطه را وارد کنید:
"""
    await message.answer(types_text)
    await state.set_state(AddSmartDiscountStates.waiting_type)


@router.message(AddSmartDiscountStates.waiting_type)
async def add_smart_discount_type(message: Message, state: FSMContext):
    type_map = {
        "1": DiscountType.HOURLY,
        "2": DiscountType.FIRST_PURCHASE,
        "3": DiscountType.CASHBACK,
        "4": DiscountType.BULK_PURCHASE,
        "5": DiscountType.LOYALTY,
        "6": DiscountType.SEASONAL,
        "7": DiscountType.BIRTHDAY
    }
    
    discount_type = type_map.get(message.text.strip())
    if not discount_type:
        await message.answer("نوع نامعتبر است. لطفاً عدد 1-7 را وارد کنید.")
        return
    
    await state.update_data(discount_type=discount_type)
    
    # Ask for discount value based on type
    if discount_type == DiscountType.CASHBACK:
        await message.answer("درصد کش‌بک را وارد کنید (مثال: 5 برای 5%):")
    else:
        await message.answer("درصد تخفیف را وارد کنید (مثال: 20 برای 20%):")
    
    await state.set_state(AddSmartDiscountStates.waiting_discount_value)


@router.message(AddSmartDiscountStates.waiting_discount_value)
async def add_smart_discount_value(message: Message, state: FSMContext):
    try:
        percent = float(message.text.strip())
        if percent <= 0 or percent > 100:
            await message.answer("درصد باید بین 0 تا 100 باشد.")
            return
    except ValueError:
        await message.answer("لطفاً یک عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    discount_type = data["discount_type"]
    
    await state.update_data(percent_off=int(percent))
    
    # Ask for conditions based on type
    if discount_type == DiscountType.HOURLY:
        await message.answer("ساعات اعمال تخفیف را وارد کنید (مثال: 9,10,11,12):")
    elif discount_type == DiscountType.LOYALTY:
        await message.answer("حداقل سطح وفاداری را وارد کنید (0-5):")
    elif discount_type == DiscountType.BULK_PURCHASE:
        await message.answer("حداقل مبلغ خرید برای تخفیف را وارد کنید (تومان):")
    else:
        await message.answer("شرایط اضافی (اختیاری) - JSON یا 'none':")
    
    await state.set_state(AddSmartDiscountStates.waiting_conditions)


@router.message(AddSmartDiscountStates.waiting_conditions)
async def add_smart_discount_conditions(message: Message, state: FSMContext):
    data = await state.get_data()
    discount_type = data["discount_type"]
    
    conditions = {}
    
    if discount_type == DiscountType.HOURLY:
        try:
            hours = [int(h.strip()) for h in message.text.split(",")]
            conditions["hours"] = hours
        except ValueError:
            await message.answer("فرمت نامعتبر. مثال: 9,10,11,12")
            return
    elif discount_type == DiscountType.LOYALTY:
        try:
            level = int(message.text.strip())
            conditions["min_loyalty_level"] = level
        except ValueError:
            await message.answer("لطفاً عدد معتبر وارد کنید.")
            return
    elif discount_type == DiscountType.BULK_PURCHASE:
        try:
            amount = int(message.text.strip())
            conditions["min_purchase_amount"] = amount
        except ValueError:
            await message.answer("لطفاً عدد معتبر وارد کنید.")
            return
    elif message.text.strip().lower() != "none":
        try:
            conditions = json.loads(message.text.strip())
        except json.JSONDecodeError:
            await message.answer("فرمت JSON نامعتبر یا 'none' وارد کنید.")
            return
    
    await state.update_data(conditions=json.dumps(conditions))
    
    await message.answer("محدودیت‌های استفاده:\nحد روزانه (0 برای نامحدود):")
    await state.set_state(AddSmartDiscountStates.waiting_limits)


@router.message(AddSmartDiscountStates.waiting_limits)
async def add_smart_discount_limits(message: Message, state: FSMContext):
    try:
        daily_limit = int(message.text.strip())
        if daily_limit < 0:
            await message.answer("حد روزانه نمی‌تواند منفی باشد.")
            return
    except ValueError:
        await message.answer("لطفاً عدد معتبر وارد کنید.")
        return
    
    await state.update_data(daily_limit=daily_limit if daily_limit > 0 else None)
    
    await message.answer("حد کل (0 برای نامحدود):")
    # Continue with total limit
    await state.set_state(AddSmartDiscountStates.waiting_targets)


@router.message(AddSmartDiscountStates.waiting_targets)
async def add_smart_discount_targets(message: Message, state: FSMContext):
    try:
        total_limit = int(message.text.strip())
        if total_limit < 0:
            await message.answer("حد کل نمی‌تواند منفی باشد.")
            return
    except ValueError:
        await message.answer("لطفاً عدد معتبر وارد کنید.")
        return
    
    data = await state.get_data()
    
    async with get_db_session() as session:
        smart_discount = SmartDiscount(
            name=data["name"],
            discount_type=data["discount_type"],
            percent_off=data["percent_off"],
            trigger_conditions=data["conditions"],
            daily_limit=data["daily_limit"],
            total_limit=total_limit if total_limit > 0 else None,
            is_active=True,
            priority=0
        )
        session.add(smart_discount)
    
    await state.clear()
    await message.answer("✅ تخفیف هوشمند با موفقیت اضافه شد!")


@router.message(Command("list_smart_discounts"))
async def list_smart_discounts(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        discounts = (await session.execute(
            select(SmartDiscount).order_by(SmartDiscount.priority.desc(), SmartDiscount.created_at.desc())
        )).scalars().all()
    
    if not discounts:
        await message.answer("تخفیف هوشمندی ثبت نشده است.")
        return
    
    out = []
    for d in discounts:
        status = "✅" if d.is_active else "❌"
        type_emoji = {
            DiscountType.HOURLY: "🕐",
            DiscountType.FIRST_PURCHASE: "🎯",
            DiscountType.CASHBACK: "💰",
            DiscountType.BULK_PURCHASE: "📦",
            DiscountType.LOYALTY: "⭐",
            DiscountType.SEASONAL: "🌸",
            DiscountType.BIRTHDAY: "🎂"
        }.get(d.discount_type, "❓")
        
        usage_info = f"{d.used_count}/{d.total_limit or '∞'}"
        daily_info = f"{d.daily_used_count}/{d.daily_limit or '∞'}"
        
        out.append(f"{status} {type_emoji} {d.name}\n"
                  f"   نوع: {d.discount_type}\n"
                  f"   تخفیف: {d.percent_off}%\n"
                  f"   استفاده: {usage_info} (روزانه: {daily_info})")
    
    await message.answer("\n\n".join(out))


@router.message(Command("smart_discount_stats"))
async def smart_discount_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        
        # Overall stats
        total_discounts = (await session.execute(
            select(func.count(SmartDiscount.id))
        )).scalar()
        
        active_discounts = (await session.execute(
            select(func.count(SmartDiscount.id))
            .where(SmartDiscount.is_active == True)
        )).scalar()
        
        total_usage = (await session.execute(
            select(func.sum(SmartDiscount.used_count))
        )).scalar() or 0
        
        # Type breakdown
        type_stats = (await session.execute(
            select(SmartDiscount.discount_type, func.count(SmartDiscount.id))
            .group_by(SmartDiscount.discount_type)
        )).all()
        
        # Top performing discounts
        top_discounts = (await session.execute(
            select(SmartDiscount.name, SmartDiscount.used_count)
            .order_by(SmartDiscount.used_count.desc())
            .limit(5)
        )).all()
    
    stats_text = f"""
📊 آمار تخفیف‌های هوشمند:

📈 کلی:
• کل تخفیف‌ها: {total_discounts}
• تخفیف‌های فعال: {active_discounts}
• کل استفاده: {total_usage}

📊 بر اساس نوع:
"""
    
    for discount_type, count in type_stats:
        type_name = {
            DiscountType.HOURLY: "ساعتی",
            DiscountType.FIRST_PURCHASE: "خرید اول",
            DiscountType.CASHBACK: "کش‌بک",
            DiscountType.BULK_PURCHASE: "خرید عمده",
            DiscountType.LOYALTY: "وفاداری",
            DiscountType.SEASONAL: "فصلی",
            DiscountType.BIRTHDAY: "تولد"
        }.get(discount_type, discount_type)
        stats_text += f"• {type_name}: {count}\n"
    
    stats_text += "\n🏆 پرفروش‌ترین تخفیف‌ها:\n"
    for i, (name, usage) in enumerate(top_discounts, 1):
        stats_text += f"{i}. {name}: {usage} استفاده\n"
    
    await message.answer(stats_text)


@router.message(Command("user_discount_profile"))
async def user_discount_profile(message: Message):
    """Get user's discount profile and available discounts"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        summary = await SmartDiscountService.get_user_discount_summary(session, user.id)
        profile = summary["profile"]
    
    profile_text = f"""
🎯 پروفایل تخفیف شما:

⭐ سطح وفاداری: {profile.loyalty_level}/5
🛒 کل خریدها: {profile.total_purchases}
💰 کل هزینه: {profile.total_spent:,.0f} تومان
🎁 کل صرفه‌جویی: {profile.total_discount_savings:,.0f} تومان
💸 کل کش‌بک: {profile.total_cashback_earned:,.0f} تومان
⏳ کش‌بک در انتظار: {summary['pending_cashback']:,.0f} تومان

📅 اولین خرید: {profile.first_purchase_date.strftime('%Y/%m/%d') if profile.first_purchase_date else 'هنوز خرید نکرده‌اید'}
📅 آخرین خرید: {profile.last_purchase_date.strftime('%Y/%m/%d') if profile.last_purchase_date else 'هنوز خرید نکرده‌اید'}

🎂 ماه تولد: {profile.birthday_month or 'تنظیم نشده'}
"""
    
    # Add recent usage
    if summary["recent_usage"]:
        profile_text += "\n📋 آخرین تخفیف‌ها:\n"
        for usage in summary["recent_usage"][:5]:
            date_str = usage.applied_at.strftime('%m/%d')
            profile_text += f"• {usage.discount_amount:,.0f} تومان صرفه‌جویی ({date_str})\n"
    
    await message.answer(profile_text)


@router.message(Command("set_birthday"))
async def set_birthday_start(message: Message, state: FSMContext):
    await message.answer("ماه تولد خود را وارد کنید (1-12):")
    await state.set_state("waiting_birthday_month")


@router.message(F.text.regexp(r'^([1-9]|1[0-2])$'))
async def set_birthday_month(message: Message, state: FSMContext):
    if await state.get_state() != "waiting_birthday_month":
        return
    
    month = int(message.text.strip())
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        # Update user profile
        from models.smart_discounts import UserDiscountProfile
        profile = (await session.execute(
            select(UserDiscountProfile).where(UserDiscountProfile.user_id == user.id)
        )).scalar_one_or_none()
        
        if not profile:
            profile = UserDiscountProfile(user_id=user.id)
            session.add(profile)
        
        profile.birthday_month = month
    
    await state.clear()
    
    month_names = [
        "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
    ]
    
    await message.answer(f"✅ ماه تولد شما به {month_names[month-1]} تنظیم شد!\nدر ماه تولدتان تخفیف ویژه دریافت خواهید کرد.")


@router.message(Command("available_discounts"))
async def available_discounts(message: Message):
    """Show available discounts for user"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        # Get eligible discounts for a sample purchase
        eligible_discounts = await SmartDiscountService.get_eligible_discounts(
            session, user.id, 100000  # Sample 100K purchase
        )
    
    if not eligible_discounts:
        await message.answer("در حال حاضر تخفیف خاصی برای شما موجود نیست.")
        return
    
    discounts_text = "🎁 تخفیف‌های موجود برای شما:\n\n"
    
    for discount in eligible_discounts:
        type_emoji = {
            DiscountType.HOURLY: "🕐",
            DiscountType.FIRST_PURCHASE: "🎯",
            DiscountType.CASHBACK: "💰",
            DiscountType.BULK_PURCHASE: "📦",
            DiscountType.LOYALTY: "⭐",
            DiscountType.SEASONAL: "🌸",
            DiscountType.BIRTHDAY: "🎂"
        }.get(discount.discount_type, "❓")
        
        type_name = {
            DiscountType.HOURLY: "تخفیف ساعتی",
            DiscountType.FIRST_PURCHASE: "تخفیف خرید اول",
            DiscountType.CASHBACK: "کش‌بک",
            DiscountType.BULK_PURCHASE: "تخفیف خرید عمده",
            DiscountType.LOYALTY: "تخفیف وفاداری",
            DiscountType.SEASONAL: "تخفیف فصلی",
            DiscountType.BIRTHDAY: "تخفیف تولد"
        }.get(discount.discount_type, discount.discount_type)
        
        discounts_text += f"{type_emoji} {discount.name}\n"
        discounts_text += f"   نوع: {type_name}\n"
        discounts_text += f"   تخفیف: {discount.percent_off}%\n"
        
        if discount.min_purchase_amount:
            discounts_text += f"   حداقل خرید: {discount.min_purchase_amount:,} تومان\n"
        
        if discount.daily_limit:
            remaining = discount.daily_limit - discount.daily_used_count
            discounts_text += f"   باقی‌مانده امروز: {remaining}\n"
        
        discounts_text += "\n"
    
    await message.answer(discounts_text)


# Admin commands for cashback management
@router.message(Command("list_cashback_rules"))
async def list_cashback_rules(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        rules = (await session.execute(
            select(CashbackRule).order_by(CashbackRule.created_at.desc())
        )).scalars().all()
    
    if not rules:
        await message.answer("قانون کش‌بکی ثبت نشده است.")
        return
    
    out = []
    for rule in rules:
        status = "✅" if rule.is_active else "❌"
        cashback_info = f"{rule.percent_cashback}%" if rule.percent_cashback > 0 else f"{rule.fixed_cashback:,} تومان"
        
        out.append(f"{status} {rule.name}\n"
                  f"   کش‌بک: {cashback_info}\n"
                  f"   شرط: {rule.trigger_type} = {rule.trigger_value}\n"
                  f"   استفاده: {rule.used_count}")
    
    await message.answer("\n\n".join(out))


@router.message(Command("cashback_stats"))
async def cashback_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        
        # Cashback statistics
        total_rules = (await session.execute(
            select(func.count(CashbackRule.id))
        )).scalar()
        
        active_rules = (await session.execute(
            select(func.count(CashbackRule.id))
            .where(CashbackRule.is_active == True)
        )).scalar()
        
        total_cashback_paid = (await session.execute(
            select(func.sum(CashbackTransaction.cashback_amount))
            .where(CashbackTransaction.status == "paid")
        )).scalar() or 0
        
        pending_cashback = (await session.execute(
            select(func.sum(CashbackTransaction.cashback_amount))
            .where(CashbackTransaction.status == "pending")
        )).scalar() or 0
    
    stats_text = f"""
💰 آمار کش‌بک:

📊 کلی:
• کل قوانین: {total_rules}
• قوانین فعال: {active_rules}
• کش‌بک پرداخت شده: {total_cashback_paid:,.0f} تومان
• کش‌بک در انتظار: {pending_cashback:,.0f} تومان
"""
    
    await message.answer(stats_text)