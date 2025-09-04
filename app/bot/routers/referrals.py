from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.content import ContentItem
from models.referrals import ReferralEvent
from models.billing import Transaction
from bot.inline import user_profile_actions_kb
from bot.keyboards import main_menu_kb


router = Router(name="referrals")


@router.message(F.text == "دعوت دوستان")
async def referrals_menu(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select, func
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
        
        # Get referral statistics
        referral_count = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.referred_by_user_id == me.id)
        )).scalar() or 0
        
        total_bonus = (await session.execute(
            select(func.sum(ReferralEvent.bonus_amount))
            .where(ReferralEvent.referrer_user_id == me.id)
        )).scalar() or 0
        
        # Get recent referrals
        recent_referrals = (await session.execute(
            select(TelegramUser)
            .where(TelegramUser.referred_by_user_id == me.id)
            .order_by(TelegramUser.created_at.desc())
            .limit(5)
        )).scalars().all()
        
        ref_text = (
            await session.execute(select(ContentItem).where(ContentItem.key == "ref_text"))
        ).scalar_one_or_none()
        banner = (
            await session.execute(select(ContentItem).where(ContentItem.key == "ref_banner_file_id"))
        ).scalar_one_or_none()

    if not settings.bot_username:
        link_line = "لطفاً bot_username را در تنظیمات قرار دهید."
    else:
        link = f"https://t.me/{settings.bot_username}?start=ref_{me.telegram_user_id}"
        link_line = f"🔗 لینک دعوت اختصاصی شما:\n{link}"

    # Build referral info text
    text = f"""
🎁 سیستم دعوت دوستان

📊 آمار شما:
👥 تعداد دعوت‌ها: {referral_count}
💰 مجموع پاداش: {total_bonus:,.0f} تومان
🎯 درصد پاداش: {settings.referral_percent}%
💵 پاداش ثابت: {settings.referral_fixed:,} تومان

{link_line}

📝 نحوه کار:
• دوستان خود را با لینک بالا دعوت کنید
• هر خرید دوستان شما = پاداش برای شما
• پاداش = {settings.referral_percent}% از مبلغ خرید + {settings.referral_fixed:,} تومان
• پاداش به صورت خودکار به کیف پول شما اضافه می‌شود
    """.strip()
    
    if recent_referrals:
        text += "\n\n👥 آخرین دعوت‌ها:\n"
        for ref in recent_referrals:
            text += f"• {ref.first_name or 'بدون نام'} (@{ref.username or 'بدون نام کاربری'})\n"
    
    # Add custom referral text if available
    if ref_text and ref_text.text:
        text = f"{ref_text.text}\n\n{text}"
    
    if banner and banner.file_id:
        try:
            await message.answer_photo(photo=banner.file_id, caption=text)
            return
        except Exception:
            pass
    
    await message.answer(text, reply_markup=main_menu_kb())

