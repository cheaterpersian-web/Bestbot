from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.advanced_reseller import ResellerLevel, ResellerStatus
from services.advanced_reseller_service import AdvancedResellerService


router = Router(name="advanced_reseller")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class ResellerApplicationStates(StatesGroup):
    waiting_business_name = State()
    waiting_business_type = State()
    waiting_contact_info = State()
    waiting_parent_reseller = State()


# User-side reseller features
@router.message(Command("become_reseller"))
async def become_reseller_start(message: Message, state: FSMContext):
    """Start reseller application process"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        # Check if already a reseller
        from models.advanced_reseller import AdvancedReseller
        existing_reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.user_id == user.id)
        )).scalar_one_or_none()
        
        if existing_reseller:
            status_text = {
                ResellerStatus.PENDING: "در انتظار تایید",
                ResellerStatus.ACTIVE: "فعال",
                ResellerStatus.SUSPENDED: "معلق",
                ResellerStatus.TERMINATED: "فسخ شده",
                ResellerStatus.BLACKLISTED: "سیاه‌لیست"
            }.get(existing_reseller.status, "نامشخص")
            
            await message.answer(f"شما قبلاً درخواست نمایندگی داده‌اید.\nوضعیت: {status_text}")
            return
    
    await message.answer("🏢 درخواست نمایندگی\n\nنام کسب‌وکار خود را وارد کنید:")
    await state.set_state(ResellerApplicationStates.waiting_business_name)


@router.message(ResellerApplicationStates.waiting_business_name)
async def reseller_business_name(message: Message, state: FSMContext):
    await state.update_data(business_name=message.text.strip())
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 شخصی", callback_data="business_type:individual")],
        [InlineKeyboardButton(text="🏢 شرکتی", callback_data="business_type:company")]
    ])
    
    await message.answer("نوع کسب‌وکار خود را انتخاب کنید:", reply_markup=kb)
    await state.set_state(ResellerApplicationStates.waiting_business_type)


@router.callback_query(F.data.startswith("business_type:"))
async def reseller_business_type(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != ResellerApplicationStates.waiting_business_type:
        return
    
    business_type = callback.data.split(":")[1]
    await state.update_data(business_type=business_type)
    
    await callback.message.edit_text("📞 اطلاعات تماس:\n\nشماره تلفن خود را وارد کنید:")
    await state.set_state(ResellerApplicationStates.waiting_contact_info)
    await callback.answer()


@router.message(ResellerApplicationStates.waiting_contact_info)
async def reseller_contact_info(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(contact_phone=phone)
    
    await message.answer("📧 آدرس ایمیل خود را وارد کنید (اختیاری):")
    # Continue to next step
    await state.set_state(ResellerApplicationStates.waiting_parent_reseller)


@router.message(ResellerApplicationStates.waiting_parent_reseller)
async def reseller_parent_reseller(message: Message, state: FSMContext):
    email = message.text.strip() if message.text.strip() else None
    await state.update_data(contact_email=email)
    
    # Check if user has a referral code
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        if user.referred_by_user_id:
            # Check if referrer is a reseller
            from models.advanced_reseller import AdvancedReseller
            parent_reseller = (await session.execute(
                select(AdvancedReseller).where(
                    and_(
                        AdvancedReseller.user_id == user.referred_by_user_id,
                        AdvancedReseller.status == ResellerStatus.ACTIVE
                    )
                )
            )).scalar_one_or_none()
            
            if parent_reseller:
                await state.update_data(parent_reseller_id=parent_reseller.id)
    
    data = await state.get_data()
    
    # Create reseller application
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            reseller = await AdvancedResellerService.create_reseller(
                session=session,
                user_id=user.id,
                business_name=data["business_name"],
                business_type=data["business_type"],
                parent_reseller_id=data.get("parent_reseller_id")
            )
            
            # Update contact info
            reseller.contact_phone = data["contact_phone"]
            reseller.contact_email = data.get("contact_email")
        
        await state.clear()
        
        parent_info = ""
        if data.get("parent_reseller_id"):
            parent_info = "\n\n✅ شما تحت نمایندگی یک نماینده فعال قرار خواهید گرفت."
        
        await message.answer(f"✅ درخواست نمایندگی شما ثبت شد!\n\n"
                           f"نام کسب‌وکار: {data['business_name']}\n"
                           f"نوع: {data['business_type']}\n"
                           f"تلفن: {data['contact_phone']}{parent_info}\n\n"
                           f"درخواست شما در حال بررسی است و به زودی نتیجه اعلام خواهد شد.")
        
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ خطا در ثبت درخواست: {str(e)}")


@router.message(Command("my_reseller_profile"))
async def my_reseller_profile(message: Message):
    """Show user's reseller profile"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        from models.advanced_reseller import AdvancedReseller
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.user_id == user.id)
        )).scalar_one_or_none()
        
        if not reseller:
            await message.answer("شما نماینده نیستید.")
            return
        
        analytics = await AdvancedResellerService.get_reseller_analytics(session, reseller.id)
    
    level_emojis = {
        ResellerLevel.BRONZE: "🥉",
        ResellerLevel.SILVER: "🥈",
        ResellerLevel.GOLD: "🥇",
        ResellerLevel.PLATINUM: "💎",
        ResellerLevel.DIAMOND: "💠"
    }
    
    status_text = {
        ResellerStatus.PENDING: "در انتظار تایید",
        ResellerStatus.ACTIVE: "فعال",
        ResellerStatus.SUSPENDED: "معلق",
        ResellerStatus.TERMINATED: "فسخ شده",
        ResellerStatus.BLACKLISTED: "سیاه‌لیست"
    }
    
    profile_text = f"""
🏢 پروفایل نمایندگی شما:

{level_emojis.get(reseller.level, "❓")} سطح: {reseller.level.value.title()}
📊 وضعیت: {status_text.get(reseller.status, "نامشخص")}
🏢 کسب‌وکار: {reseller.business_name or 'تنظیم نشده'}

💰 عملکرد مالی:
• کل فروش: {reseller.total_sales:,.0f} تومان
• کل کمیسیون: {reseller.total_commission_earned:,.0f} تومان
• موجودی: {reseller.wallet_balance:,.0f} تومان
• در انتظار: {reseller.pending_commission:,.0f} تومان

👥 مشتریان و زیرنمایندگان:
• کل مشتریان: {reseller.total_customers}
• زیرنمایندگان: {reseller.total_sub_resellers}/{reseller.max_sub_resellers}

📈 عملکرد ماهانه:
• فروش ماهانه: {reseller.monthly_sales:,.0f} تومان
• کمیسیون ماهانه: {reseller.monthly_commission:,.0f} تومان
"""
    
    if analytics["current_target"]:
        target = analytics["current_target"]
        achievement_rate = (target.sales_achieved / target.sales_target * 100) if target.sales_target > 0 else 0
        profile_text += f"\n🎯 هدف ماهانه:\n"
        profile_text += f"• فروش: {target.sales_achieved:,.0f}/{target.sales_target:,.0f} تومان ({achievement_rate:.1f}%)\n"
        profile_text += f"• مشتریان: {target.customers_achieved}/{target.customer_target}\n"
        
        if target.is_achieved:
            profile_text += f"• 🎉 هدف محقق شد! پاداش: {target.bonus_amount:,.0f} تومان\n"
    
    await message.answer(profile_text)


@router.message(Command("reseller_commissions"))
async def reseller_commissions(message: Message):
    """Show reseller commissions"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        from models.advanced_reseller import AdvancedReseller
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.user_id == user.id)
        )).scalar_one_or_none()
        
        if not reseller:
            await message.answer("شما نماینده نیستید.")
            return
        
        from models.advanced_reseller import ResellerCommission
        recent_commissions = (await session.execute(
            select(ResellerCommission)
            .where(ResellerCommission.reseller_id == reseller.id)
            .order_by(ResellerCommission.created_at.desc())
            .limit(10)
        )).scalars().all()
    
    if not recent_commissions:
        await message.answer("هیچ کمیسیونی دریافت نکرده‌اید.")
        return
    
    commissions_text = "💰 کمیسیون‌های شما:\n\n"
    
    for i, commission in enumerate(recent_commissions, 1):
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "paid": "💰"
        }.get(commission.status, "❓")
        
        date_str = commission.created_at.strftime('%m/%d %H:%M')
        level_text = f"سطح {commission.level}" if commission.level > 1 else "مستقیم"
        
        commissions_text += f"{i}. {status_emoji} {commission.commission_amount:,.0f} تومان\n"
        commissions_text += f"   {level_text} - {date_str}\n\n"
    
    await message.answer(commissions_text)


@router.message(Command("reseller_hierarchy"))
async def reseller_hierarchy(message: Message):
    """Show reseller hierarchy"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        from models.advanced_reseller import AdvancedReseller
        reseller = (await session.execute(
            select(AdvancedReseller).where(AdvancedReseller.user_id == user.id)
        )).scalar_one_or_none()
        
        if not reseller:
            await message.answer("شما نماینده نیستید.")
            return
        
        hierarchy = await AdvancedResellerService.get_reseller_hierarchy(session, reseller.id)
    
    def format_hierarchy(hierarchy_data, level=0):
        if not hierarchy_data:
            return ""
        
        indent = "  " * level
        reseller = hierarchy_data["reseller"]
        user = hierarchy_data.get("user")
        
        text = f"{indent}🏢 {reseller.business_name or 'بدون نام'}\n"
        text += f"{indent}   سطح: {reseller.level.value}\n"
        text += f"{indent}   فروش: {reseller.total_sales:,.0f} تومان\n"
        
        for sub in hierarchy_data.get("sub_resellers", []):
            text += format_hierarchy(sub, level + 1)
        
        return text
    
    hierarchy_text = "🌳 سلسله مراتب نمایندگی:\n\n"
    hierarchy_text += format_hierarchy(hierarchy)
    
    await message.answer(hierarchy_text)


# Admin reseller management
@router.message(Command("reseller_applications"))
async def reseller_applications(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        from models.advanced_reseller import AdvancedReseller
        
        pending_applications = (await session.execute(
            select(AdvancedReseller, TelegramUser)
            .join(TelegramUser, AdvancedReseller.user_id == TelegramUser.id)
            .where(AdvancedReseller.status == ResellerStatus.PENDING)
            .order_by(AdvancedReseller.created_at.desc())
        )).all()
    
    if not pending_applications:
        await message.answer("هیچ درخواست نمایندگی در انتظار نیست.")
        return
    
    applications_text = "📋 درخواست‌های نمایندگی:\n\n"
    
    for i, (reseller, user) in enumerate(pending_applications, 1):
        applications_text += f"{i}. @{user.username or 'بدون نام کاربری'}\n"
        applications_text += f"   کسب‌وکار: {reseller.business_name or 'بدون نام'}\n"
        applications_text += f"   نوع: {reseller.business_type}\n"
        applications_text += f"   تلفن: {reseller.contact_phone or 'ندارد'}\n"
        applications_text += f"   تاریخ: {reseller.created_at.strftime('%Y/%m/%d')}\n\n"
    
    await message.answer(applications_text)


@router.message(Command("approve_reseller"))
async def approve_reseller_start(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract reseller ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /approve_reseller <reseller_id>")
        return
    
    try:
        reseller_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه نماینده نامعتبر است.")
        return
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            reseller = await AdvancedResellerService.approve_reseller(
                session=session,
                reseller_id=reseller_id,
                approved_by=admin_user.id
            )
            
            # Get user info
            user = (await session.execute(
                select(TelegramUser).where(TelegramUser.id == reseller.user_id)
            )).scalar_one()
        
        await message.answer(f"✅ نماینده تایید شد!\n"
                           f"کاربر: @{user.username or 'بدون نام کاربری'}\n"
                           f"کسب‌وکار: {reseller.business_name}")
        
    except Exception as e:
        await message.answer(f"❌ خطا در تایید نماینده: {str(e)}")


@router.message(Command("reseller_stats"))
async def reseller_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select, func
        from models.advanced_reseller import AdvancedReseller
        
        # Overall stats
        total_resellers = (await session.execute(
            select(func.count(AdvancedReseller.id))
        )).scalar()
        
        active_resellers = (await session.execute(
            select(func.count(AdvancedReseller.id))
            .where(AdvancedReseller.status == ResellerStatus.ACTIVE)
        )).scalar()
        
        pending_resellers = (await session.execute(
            select(func.count(AdvancedReseller.id))
            .where(AdvancedReseller.status == ResellerStatus.PENDING)
        )).scalar()
        
        # Level distribution
        level_stats = (await session.execute(
            select(AdvancedReseller.level, func.count(AdvancedReseller.id))
            .group_by(AdvancedReseller.level)
        )).all()
        
        # Top performers
        top_resellers = (await session.execute(
            select(AdvancedReseller, TelegramUser)
            .join(TelegramUser, AdvancedReseller.user_id == TelegramUser.id)
            .where(AdvancedReseller.status == ResellerStatus.ACTIVE)
            .order_by(AdvancedReseller.total_sales.desc())
            .limit(5)
        )).all()
    
    stats_text = f"""
📊 آمار نمایندگان:

📈 کلی:
• کل نمایندگان: {total_resellers}
• فعال: {active_resellers}
• در انتظار: {pending_resellers}

🏆 توزیع سطح:
"""
    
    level_names = {
        ResellerLevel.BRONZE: "برنزی",
        ResellerLevel.SILVER: "نقره‌ای",
        ResellerLevel.GOLD: "طلایی",
        ResellerLevel.PLATINUM: "پلاتینیوم",
        ResellerLevel.DIAMOND: "الماس"
    }
    
    for level, count in level_stats:
        level_name = level_names.get(level, level.value)
        stats_text += f"• {level_name}: {count}\n"
    
    stats_text += "\n🏆 برترین نمایندگان:\n"
    for i, (reseller, user) in enumerate(top_resellers, 1):
        stats_text += f"{i}. @{user.username or 'بدون نام کاربری'}\n"
        stats_text += f"   فروش: {reseller.total_sales:,.0f} تومان\n"
        stats_text += f"   سطح: {reseller.level.value}\n\n"
    
    await message.answer(stats_text)


@router.message(Command("process_commissions"))
async def process_commissions(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            admin_user = (await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
            )).scalar_one()
            
            # Get resellers with pending commissions
            from models.advanced_reseller import AdvancedReseller
            resellers_with_commissions = (await session.execute(
                select(AdvancedReseller)
                .where(
                    and_(
                        AdvancedReseller.status == ResellerStatus.ACTIVE,
                        AdvancedReseller.pending_commission > 0
                    )
                )
            )).scalars().all()
            
            processed_count = 0
            total_amount = 0
            
            for reseller in resellers_with_commissions:
                try:
                    payment = await AdvancedResellerService.process_commission_payment(
                        session=session,
                        reseller_id=reseller.id,
                        payment_method="wallet",
                        processed_by=admin_user.id,
                        notes="پرداخت خودکار کمیسیون"
                    )
                    processed_count += 1
                    total_amount += payment.amount
                except Exception as e:
                    print(f"Error processing commission for reseller {reseller.id}: {e}")
        
        await message.answer(f"✅ پردازش کمیسیون‌ها تکمیل شد!\n"
                           f"نمایندگان پردازش شده: {processed_count}\n"
                           f"کل مبلغ: {total_amount:,.0f} تومان")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش کمیسیون‌ها: {str(e)}")


@router.message(Command("reseller_help"))
async def reseller_help(message: Message):
    help_text = """
🏢 راهنمای سیستم نمایندگی:

👤 دستورات کاربری:
• /become_reseller - درخواست نمایندگی
• /my_reseller_profile - پروفایل نمایندگی
• /reseller_commissions - کمیسیون‌ها
• /reseller_hierarchy - سلسله مراتب

🔧 دستورات ادمین:
• /reseller_applications - درخواست‌های نمایندگی
• /approve_reseller <id> - تایید نماینده
• /reseller_stats - آمار نمایندگان
• /process_commissions - پردازش کمیسیون‌ها

🏆 سطوح نمایندگی:
• 🥉 برنزی - شروع کار
• 🥈 نقره‌ای - فروش متوسط
• 🥇 طلایی - فروش بالا
• 💎 پلاتینیوم - فروش بسیار بالا
• 💠 الماس - بالاترین سطح

💰 کمیسیون‌ها:
• کمیسیون مستقیم (سطح 1): 100%
• کمیسیون زیرنماینده (سطح 2): 50%
• کمیسیون زیرزیرنماینده (سطح 3): 25%

🎯 ویژگی‌ها:
• سلسله مراتب چندسطحه
• کمیسیون پلکانی
• هدف‌گذاری ماهانه
• پاداش دستیابی به هدف
• مدیریت زیرنمایندگان
• گزارش‌گیری پیشرفته
"""
    
    await message.answer(help_text)