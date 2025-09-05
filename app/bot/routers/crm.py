from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.crm import UserSegment, ActivityType, CRMCampaign
from models.user import TelegramUser
from services.crm_service import CRMService


router = Router(name="crm")


async def _is_admin(telegram_id: int) -> bool:
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id))
        ).scalar_one_or_none()
        return bool(user and user.is_admin)


class CreateCRMCampaignStates(StatesGroup):
    waiting_name = State()
    waiting_type = State()
    waiting_content = State()
    waiting_target = State()
    waiting_schedule = State()


# User-side CRM features
@router.message(Command("my_profile"))
async def my_profile(message: Message):
    """Show user's CRM profile"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        analytics = await CRMService.get_user_analytics(session, user.id)
        profile = analytics["profile"]
    
    profile_text = f"""
👤 پروفایل شخصی شما:

⭐ سطح وفاداری: {profile.primary_segment.value}
🎯 مرحله زندگی: {profile.lifecycle_stage}
📊 امتیاز تعامل: {profile.engagement_score:.1f}/1.0
⚠️ احتمال ترک: {profile.churn_probability:.1f}/1.0

📈 آمار فعالیت:
• فرکانس ورود: {profile.login_frequency} بار در هفته
• فرکانس خرید: {profile.purchase_frequency:.1f} بار در ماه
• میانگین خرید: {profile.avg_purchase_amount:,.0f} تومان

📅 آخرین فعالیت: {profile.last_activity_at.strftime('%Y/%m/%d %H:%M') if profile.last_activity_at else 'هیچ فعالیتی ثبت نشده'}
⏰ روزهای بدون فعالیت: {profile.days_since_last_activity}
"""
    
    # Add insights
    if analytics["insights"]:
        profile_text += "\n💡 بینش‌های شخصی:\n"
        for insight in analytics["insights"][:3]:
            profile_text += f"• {insight.title}\n"
    
    # Add offers
    if analytics["offers"]:
        profile_text += "\n🎁 پیشنهادات ویژه:\n"
        for offer in analytics["offers"][:2]:
            profile_text += f"• {offer.title}\n"
    
    await message.answer(profile_text)


@router.message(Command("my_offers"))
async def my_offers(message: Message):
    """Show personalized offers"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        offers = await CRMService.generate_personalized_offers(session, user.id)
    
    if not offers:
        await message.answer("در حال حاضر پیشنهاد خاصی برای شما موجود نیست.")
        return
    
    offers_text = "🎁 پیشنهادات شخصی‌سازی شده:\n\n"
    
    for i, offer in enumerate(offers, 1):
        offers_text += f"{i}. {offer.title}\n"
        offers_text += f"   {offer.description}\n"
        
        if offer.discount_percent:
            offers_text += f"   تخفیف: {offer.discount_percent}%\n"
        elif offer.discount_amount:
            offers_text += f"   تخفیف: {offer.discount_amount:,} تومان\n"
        elif offer.bonus_amount:
            offers_text += f"   پاداش: {offer.bonus_amount:,} تومان\n"
        
        valid_until = offer.valid_to.strftime('%Y/%m/%d')
        offers_text += f"   اعتبار تا: {valid_until}\n\n"
    
    await message.answer(offers_text)


@router.message(Command("my_insights"))
async def my_insights(message: Message):
    """Show user insights"""
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id)
        )).scalar_one()
        
        insights = await CRMService.get_user_insights(session, user.id)
    
    if not insights:
        await message.answer("در حال حاضر بینش خاصی برای شما تولید نشده است.")
        return
    
    insights_text = "💡 بینش‌های شخصی شما:\n\n"
    
    for i, insight in enumerate(insights, 1):
        confidence = "🔴" if insight.confidence_score < 0.5 else "🟡" if insight.confidence_score < 0.8 else "🟢"
        insights_text += f"{i}. {insight.title}\n"
        insights_text += f"   {insight.description}\n"
        insights_text += f"   اعتماد: {confidence} {insight.confidence_score:.1f}\n\n"
    
    await message.answer(insights_text)


# Admin CRM features
@router.message(Command("crm_dashboard"))
async def crm_dashboard(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        analytics = await CRMService.get_segment_analytics(session)
    
    dashboard_text = f"""
📊 داشبورد CRM:

👥 تقسیم‌بندی کاربران:
"""
    
    segment_names = {
        UserSegment.NEW_USER: "کاربران جدید",
        UserSegment.ACTIVE_USER: "کاربران فعال",
        UserSegment.VIP_USER: "کاربران VIP",
        UserSegment.CHURNED_USER: "کاربران ترک کرده",
        UserSegment.HIGH_VALUE: "کاربران با ارزش بالا",
        UserSegment.LOW_VALUE: "کاربران با ارزش پایین",
        UserSegment.FREQUENT_BUYER: "خریداران مکرر",
        UserSegment.OCCASIONAL_BUYER: "خریداران گاه‌به‌گاه"
    }
    
    for segment, count in analytics["segment_counts"].items():
        segment_name = segment_names.get(segment, segment)
        dashboard_text += f"• {segment_name}: {count}\n"
    
    dashboard_text += f"\n🎯 مراحل زندگی:\n"
    lifecycle_names = {
        "new": "جدید",
        "active": "فعال",
        "at_risk": "در خطر",
        "churned": "ترک کرده"
    }
    
    for stage, count in analytics["lifecycle_counts"].items():
        stage_name = lifecycle_names.get(stage, stage)
        dashboard_text += f"• {stage_name}: {count}\n"
    
    dashboard_text += f"\n📈 توزیع تعامل:\n"
    engagement_names = {
        "high": "بالا",
        "medium": "متوسط",
        "low": "پایین"
    }
    
    for level, count in analytics["engagement_distribution"].items():
        level_name = engagement_names.get(level, level)
        dashboard_text += f"• {level_name}: {count}\n"
    
    await message.answer(dashboard_text)


@router.message(Command("user_analytics"))
async def user_analytics_command(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    # Extract user ID from command
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("فرمت: /user_analytics <user_id>")
        return
    
    try:
        user_id = int(command_parts[1])
    except ValueError:
        await message.answer("شناسه کاربر نامعتبر است.")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        user = (await session.execute(
            select(TelegramUser).where(TelegramUser.id == user_id)
        )).scalar_one_or_none()
        
        if not user:
            await message.answer("کاربر یافت نشد.")
            return
        
        analytics = await CRMService.get_user_analytics(session, user_id)
        profile = analytics["profile"]
    
    analytics_text = f"""
📊 تحلیل کاربر: @{user.username or 'بدون نام کاربری'}

👤 پروفایل:
• شناسه: {user.telegram_user_id}
• نام: {user.first_name} {user.last_name or ''}
• عضویت: {user.created_at.strftime('%Y/%m/%d')}

🎯 CRM:
• بخش: {profile.primary_segment.value}
• مرحله: {profile.lifecycle_stage}
• تعامل: {profile.engagement_score:.2f}
• خطر ترک: {profile.churn_probability:.2f}

💰 مالی:
• موجودی: {user.wallet_balance:,.0f} تومان
• کل هزینه: {user.total_spent:,.0f} تومان
• سرویس‌ها: {user.total_services}

📈 فعالیت:
• ورود/هفته: {profile.login_frequency}
• خرید/ماه: {profile.purchase_frequency:.1f}
• میانگین خرید: {profile.avg_purchase_amount:,.0f} تومان
• آخرین فعالیت: {profile.last_activity_at.strftime('%Y/%m/%d %H:%M') if profile.last_activity_at else 'هیچ'}
"""
    
    # Add recent activities
    if analytics["recent_activities"]:
        analytics_text += "\n📋 آخرین فعالیت‌ها:\n"
        for activity in analytics["recent_activities"][:5]:
            date_str = activity.created_at.strftime('%m/%d %H:%M')
            analytics_text += f"• {activity.activity_type.value}: {activity.description} ({date_str})\n"
    
    # Add insights
    if analytics["insights"]:
        analytics_text += "\n💡 بینش‌ها:\n"
        for insight in analytics["insights"][:3]:
            analytics_text += f"• {insight.title} (اعتماد: {insight.confidence_score:.1f})\n"
    
    await message.answer(analytics_text)


@router.message(Command("create_campaign"))
async def create_campaign_start(message: Message, state: FSMContext):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    await message.answer("نام کمپین را وارد کنید:")
    await state.set_state(CreateCRMCampaignStates.waiting_name)


@router.message(CreateCRMCampaignStates.waiting_name)
async def create_campaign_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    
    types_text = """
نوع کمپین را انتخاب کنید:

1️⃣ پیام همگانی تلگرام
2️⃣ پیام شخصی‌سازی شده
3️⃣ اطلاع‌رسانی تخفیف
4️⃣ یادآوری تمدید
5️⃣ کمپین بازگشت

عدد مربوطه را وارد کنید:
"""
    await message.answer(types_text)
    await state.set_state(CreateCRMCampaignStates.waiting_type)


@router.message(CreateCRMCampaignStates.waiting_type)
async def create_campaign_type(message: Message, state: FSMContext):
    type_map = {
        "1": "telegram_broadcast",
        "2": "personalized_message",
        "3": "discount_notification",
        "4": "renewal_reminder",
        "5": "win_back"
    }
    
    campaign_type = type_map.get(message.text.strip())
    if not campaign_type:
        await message.answer("نوع نامعتبر است. لطفاً عدد 1-5 را وارد کنید.")
        return
    
    await state.update_data(campaign_type=campaign_type)
    await message.answer("محتوای پیام را وارد کنید:")
    await state.set_state(CreateCRMCampaignStates.waiting_content)


@router.message(CreateCRMCampaignStates.waiting_content)
async def create_campaign_content(message: Message, state: FSMContext):
    await state.update_data(message_content=message.text.strip())
    
    targets_text = """
گروه هدف را انتخاب کنید:

1️⃣ همه کاربران
2️⃣ کاربران فعال
3️⃣ کاربران VIP
4️⃣ کاربران در خطر ترک
5️⃣ کاربران ترک کرده
6️⃣ کاربران جدید

عدد مربوطه را وارد کنید:
"""
    await message.answer(targets_text)
    await state.set_state(CreateCRMCampaignStates.waiting_target)


@router.message(CreateCRMCampaignStates.waiting_target)
async def create_campaign_target(message: Message, state: FSMContext):
    target_map = {
        "1": None,  # All users
        "2": [UserSegment.ACTIVE_USER.value],
        "3": [UserSegment.VIP_USER.value],
        "4": ["at_risk"],
        "5": [UserSegment.CHURNED_USER.value],
        "6": [UserSegment.NEW_USER.value]
    }
    
    target_segments = target_map.get(message.text.strip())
    await state.update_data(target_segments=target_segments)
    
    await message.answer("زمان ارسال (YYYY-MM-DD HH:MM یا 'now' برای الان):")
    await state.set_state(CreateCRMCampaignStates.waiting_schedule)


@router.message(CreateCRMCampaignStates.waiting_schedule)
async def create_campaign_schedule(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    
    if text == "now":
        scheduled_at = None
    else:
        try:
            scheduled_at = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await message.answer("فرمت تاریخ نامعتبر است. از YYYY-MM-DD HH:MM استفاده کنید.")
            return
    
    data = await state.get_data()
    
    async with get_db_session() as session:
        campaign = await CRMService.create_campaign(
            session=session,
            name=data["name"],
            campaign_type=data["campaign_type"],
            message_content=data["message_content"],
            target_segments=data["target_segments"],
            scheduled_at=scheduled_at
        )
    
    await state.clear()
    
    schedule_text = "فوری" if scheduled_at is None else scheduled_at.strftime('%Y/%m/%d %H:%M')
    await message.answer(f"✅ کمپین '{data['name']}' ایجاد شد!\n"
                        f"زمان ارسال: {schedule_text}\n"
                        f"تعداد گیرندگان: {campaign.total_recipients}")


@router.message(Command("campaign_stats"))
async def campaign_stats(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        campaigns = (await session.execute(
            select(CRMCampaign).order_by(CRMCampaign.created_at.desc()).limit(10)
        )).scalars().all()
    
    if not campaigns:
        await message.answer("کمپینی ثبت نشده است.")
        return
    
    stats_text = "📊 آمار کمپین‌ها:\n\n"
    
    for campaign in campaigns:
        status_emoji = {
            "draft": "📝",
            "scheduled": "⏰",
            "sent": "📤",
            "completed": "✅"
        }.get(campaign.status, "❓")
        
        stats_text += f"{status_emoji} {campaign.name}\n"
        stats_text += f"   نوع: {campaign.campaign_type}\n"
        stats_text += f"   گیرندگان: {campaign.total_recipients}\n"
        stats_text += f"   ارسال شده: {campaign.delivered_count}\n"
        stats_text += f"   باز شده: {campaign.opened_count}\n"
        stats_text += f"   کلیک شده: {campaign.clicked_count}\n"
        stats_text += f"   تبدیل شده: {campaign.converted_count}\n\n"
    
    await message.answer(stats_text)


@router.message(Command("at_risk_users"))
async def at_risk_users(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        from models.crm import UserProfile
        
        at_risk_users = (await session.execute(
            select(UserProfile, TelegramUser)
            .join(TelegramUser, UserProfile.user_id == TelegramUser.id)
            .where(
                and_(
                    UserProfile.lifecycle_stage == "at_risk",
                    UserProfile.churn_probability > 0.5
                )
            )
            .order_by(UserProfile.churn_probability.desc())
            .limit(20)
        )).all()
    
    if not at_risk_users:
        await message.answer("کاربر در خطر ترک یافت نشد.")
        return
    
    risk_text = "⚠️ کاربران در خطر ترک:\n\n"
    
    for profile, user in at_risk_users:
        risk_text += f"👤 @{user.username or 'بدون نام کاربری'}\n"
        risk_text += f"   احتمال ترک: {profile.churn_probability:.1f}\n"
        risk_text += f"   روزهای بدون فعالیت: {profile.days_since_last_activity}\n"
        risk_text += f"   امتیاز تعامل: {profile.engagement_score:.1f}\n\n"
    
    await message.answer(risk_text)


@router.message(Command("update_crm_metrics"))
async def update_crm_metrics(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("دسترسی ندارید")
        return
    
    async with get_db_session() as session:
        await CRMService.update_daily_metrics(session)
    
    await message.answer("✅ معیارهای CRM به‌روزرسانی شد.")