from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from core.db import get_db_session
from models.user import TelegramUser
from models.service import Service
from models.billing import Transaction
from models.referrals import ReferralEvent
from services.payment_processor import PaymentProcessor
from bot.inline import user_profile_actions_kb
from bot.keyboards import main_menu_kb


router = Router(name="account")


class TransferStates(StatesGroup):
    waiting_target = State()
    waiting_amount = State()


@router.message(F.text == "حساب کاربری")
async def account_info(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select, func
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
        
        # Get user statistics
        config_count = (await session.execute(
            select(func.count(Service.id))
            .where(Service.user_id == me.id)
            .where(Service.is_active == True)
        )).scalar() or 0
        
        total_transactions = (await session.execute(
            select(func.count(Transaction.id))
            .where(Transaction.user_id == me.id)
        )).scalar() or 0
        
        referral_count = (await session.execute(
            select(func.count(TelegramUser.id))
            .where(TelegramUser.referred_by_user_id == me.id)
        )).scalar() or 0
        
        # Format last seen
        last_seen = "هرگز" if not me.last_seen_at else me.last_seen_at.strftime("%Y/%m/%d %H:%M")
        
        # Format registration date
        reg_date = me.created_at.strftime("%Y/%m/%d")
        
        text = f"""
👤 اطلاعات حساب کاربری

🆔 شناسه کاربری: {me.telegram_user_id}
👤 نام: {me.first_name or 'بدون نام'} {me.last_name or ''}
📱 نام کاربری: @{me.username or 'بدون نام کاربری'}
💰 موجودی کیف پول: {me.wallet_balance:,.0f} تومان

📊 آمار:
🔗 تعداد کانفیگ‌ها: {config_count}
💳 تعداد تراکنش‌ها: {total_transactions}
👥 تعداد دعوت‌ها: {referral_count}

📅 تاریخ عضویت: {reg_date}
🕐 آخرین بازدید: {last_seen}

🔗 لینک دعوت شما:
https://t.me/{message.bot.username}?start=ref_{me.telegram_user_id}
        """.strip()
        
        await message.answer(text, reply_markup=main_menu_kb())


# Transfer functionality moved to wallet.py

