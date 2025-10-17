from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery

from core.config import settings
from core.db import get_db_session
from models.billing import Transaction, PaymentCard
from models.user import TelegramUser
from services.payment_processor import PaymentProcessor
from services.fraud_detection import FraudDetectionService
from bot.inline import admin_review_tx_kb, payment_cards_kb
from bot.keyboards import wallet_menu_kb, main_menu_kb
from services.bot_settings import get_int


router = Router(name="wallet")


class TopUpStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()


class TransferStates(StatesGroup):
    waiting_for_user = State()
    waiting_for_amount = State()


@router.message(F.text == "کیف پول / پرداخت‌ها")
async def wallet_menu(message: Message, state: FSMContext):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
        
        # Get recent transactions
        recent_txs = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == me.id)
            .order_by(Transaction.created_at.desc())
            .limit(5)
        )).scalars().all()
        
        # Get payment cards
        payment_cards = await PaymentProcessor.get_all_payment_cards(session)
        
        text = f"💰 موجودی کیف پول شما: {me.wallet_balance:,.0f} تومان\n\n"
        
        if payment_cards:
            text += "💳 کارت‌های پرداخت:\n"
            for card in payment_cards[:3]:  # Show first 3 cards
                text += f"• {card.holder_name} - {card.card_number}\n"
            if len(payment_cards) > 3:
                text += f"• و {len(payment_cards) - 3} کارت دیگر...\n"
            text += "\n"
        
        min_topup = await get_int(session, "min_topup_amount", settings.min_topup_amount)
        max_topup = await get_int(session, "max_topup_amount", settings.max_topup_amount)
        text += f"برای شارژ کیف پول، مبلغ مورد نظر را ارسال کنید (تومان).\n"
        text += f"حداقل: {min_topup:,} - حداکثر: {max_topup:,}\n\n"
        
        if recent_txs:
            text += "📊 آخرین تراکنش‌ها:\n"
            for tx in recent_txs:
                status_emoji = "✅" if tx.status == "approved" else "⏳" if tx.status == "pending" else "❌"
                text += f"{status_emoji} {tx.amount:,.0f} تومان - {tx.type}\n"
        
        await message.answer(text, reply_markup=wallet_menu_kb())


@router.message(TopUpStates.waiting_for_amount, F.text.regexp(r"^\d+$"))
async def receive_amount(message: Message, state: FSMContext):
    amount = int(message.text)
    async with get_db_session() as session:
        min_topup = await get_int(session, "min_topup_amount", settings.min_topup_amount)
        max_topup = await get_int(session, "max_topup_amount", settings.max_topup_amount)
    if amount < min_topup or amount > max_topup:
        await message.answer("مبلغ نامعتبر است. دوباره ارسال کنید.")
        return
    await state.update_data(amount=amount)
    await message.answer("عکس رسید کارت‌به‌کارت را ارسال کنید.")
    await state.set_state(TopUpStates.waiting_for_receipt)


@router.message(TopUpStates.waiting_for_receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data["amount"]
    file_id = message.photo[-1].file_id

    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
        
        # Process wallet top-up with fraud detection
        tx = await PaymentProcessor.process_wallet_topup(
            session, me, amount, file_id, f"شارژ کیف پول - {amount:,.0f} تومان"
        )
        
        # Get payment card info
        payment_card = await PaymentProcessor.get_random_payment_card(session)
        
        if tx.status == "approved":
            await message.answer(
                f"✅ شارژ با موفقیت انجام شد!\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"💳 موجودی جدید: {me.wallet_balance:,.0f} تومان"
            )
        else:
            fraud_warning = ""
            if tx.fraud_score > 0.5:
                fraud_warning = "\n⚠️ این تراکنش نیاز به بررسی بیشتر دارد."
            
            await message.answer(
                f"📋 رسید دریافت شد{fraud_warning}\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"⏳ پس از بررسی ادمین، نتیجه به شما اعلام می‌شود."
            )
            
            # Notify admins
            for admin_id in settings.admin_ids:
                try:
                    fraud_info = f"\n🚨 Fraud Score: {tx.fraud_score:.2f}" if tx.fraud_score > 0 else ""
                    await message.bot.send_photo(
                        chat_id=admin_id,
                        photo=file_id,
                        caption=(
                            f"📋 رسید جدید شارژ کیف پول\n"
                            f"🆔 TX#{tx.id} | مبلغ: {amount:,} تومان\n"
                            f"👤 کاربر: {me.telegram_user_id} ({me.first_name or 'بدون نام'})\n"
                            f"💳 موجودی فعلی: {me.wallet_balance:,.0f} تومان{fraud_info}"
                        ),
                        reply_markup=admin_review_tx_kb(tx.id),
                    )
                except Exception:
                    await message.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"📋 رسید جدید شارژ کیف پول\n"
                            f"🆔 TX#{tx.id} | مبلغ: {amount:,} تومان\n"
                            f"👤 کاربر: {me.telegram_user_id} ({me.first_name or 'بدون نام'})\n"
                            f"💳 موجودی فعلی: {me.wallet_balance:,.0f} تومان"
                        ),
                        reply_markup=admin_review_tx_kb(tx.id),
                    )

    await state.clear()


@router.message(F.text == "انتقال موجودی")
async def transfer_balance_start(message: Message, state: FSMContext):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
        
        if me.wallet_balance <= 0:
            await message.answer("❌ موجودی کافی برای انتقال ندارید.")
            return
        
        await message.answer(
            f"💰 موجودی شما: {me.wallet_balance:,.0f} تومان\n\n"
            f"شناسه کاربری (User ID) مقصد را ارسال کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(TransferStates.waiting_for_user)


@router.message(TransferStates.waiting_for_user, F.text.regexp(r"^\d+$"))
async def receive_transfer_user(message: Message, state: FSMContext):
    target_user_id = int(message.text)
    
    if target_user_id == message.from_user.id:
        await message.answer("❌ نمی‌توانید موجودی را به خودتان انتقال دهید.")
        return
    
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
        target_user = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == target_user_id))).scalar_one_or_none()
        
        if not target_user:
            await message.answer("❌ کاربر مورد نظر یافت نشد.")
            return
        
        await state.update_data(target_user_id=target_user_id, target_user=target_user)
        await message.answer(
            f"👤 کاربر مقصد: {target_user.first_name or 'بدون نام'} (@{target_user.username or 'بدون نام کاربری'})\n"
            f"💰 موجودی شما: {me.wallet_balance:,.0f} تومان\n\n"
            f"مبلغ انتقال را ارسال کنید (تومان):"
        )
        await state.set_state(TransferStates.waiting_for_amount)


@router.message(TransferStates.waiting_for_amount, F.text.regexp(r"^\d+$"))
async def receive_transfer_amount(message: Message, state: FSMContext):
    amount = int(message.text)
    data = await state.get_data()
    target_user_id = data["target_user_id"]
    target_user = data["target_user"]
    
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
        
        if amount <= 0:
            await message.answer("❌ مبلغ نامعتبر است.")
            return
        
        if amount > me.wallet_balance:
            await message.answer("❌ موجودی کافی ندارید.")
            return
        
        # Process transfer
        success = await PaymentProcessor.transfer_balance(
            session, me, target_user, amount, f"انتقال از {me.telegram_user_id} به {target_user_id}"
        )
        
        if success:
            await message.answer(
                f"✅ انتقال با موفقیت انجام شد!\n"
                f"💰 مبلغ: {amount:,} تومان\n"
                f"👤 به: {target_user.first_name or 'بدون نام'}\n"
                f"💳 موجودی جدید شما: {me.wallet_balance:,.0f} تومان"
            )
            
            # Notify target user
            try:
                await message.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        f"💰 موجودی جدید دریافت کردید!\n"
                        f"💵 مبلغ: {amount:,} تومان\n"
                        f"👤 از: {me.first_name or 'بدون نام'}\n"
                        f"💳 موجودی جدید شما: {target_user.wallet_balance:,.0f} تومان"
                    )
                )
            except Exception:
                pass  # Target user might have blocked the bot
        else:
            await message.answer("❌ خطا در انتقال موجودی. لطفاً دوباره تلاش کنید.")
    
    await state.clear()


@router.message(F.text == "💰 شارژ کیف پول")
async def topup_wallet(message: Message, state: FSMContext):
    await message.answer(
        f"برای شارژ کیف پول، مبلغ مورد نظر را ارسال کنید (تومان).\n"
        f"حداقل: {settings.min_topup_amount:,} - حداکثر: {settings.max_topup_amount:,}",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(TopUpStates.waiting_for_amount)


@router.message(F.text == "📊 تاریخچه تراکنش‌ها")
async def transaction_history(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
        
        # Get all transactions
        transactions = (await session.execute(
            select(Transaction)
            .where(Transaction.user_id == me.id)
            .order_by(Transaction.created_at.desc())
            .limit(20)
        )).scalars().all()
        
        if not transactions:
            await message.answer("📝 هیچ تراکنشی یافت نشد.")
            return
        
        text = "📊 تاریخچه تراکنش‌های شما:\n\n"
        for tx in transactions:
            status_emoji = "✅" if tx.status == "approved" else "⏳" if tx.status == "pending" else "❌"
            date_str = tx.created_at.strftime("%Y/%m/%d %H:%M")
            text += f"{status_emoji} {tx.amount:,.0f} تومان\n"
            text += f"   📅 {date_str} - {tx.type}\n"
            if tx.description:
                text += f"   📝 {tx.description}\n"
            text += "\n"
        
        await message.answer(text)


@router.message(F.text == "💳 کارت‌های پرداخت")
async def show_payment_cards(message: Message):
    async with get_db_session() as session:
        payment_cards = await PaymentProcessor.get_all_payment_cards(session)
        
        if not payment_cards:
            await message.answer("💳 هیچ کارت پرداختی تعریف نشده است.")
            return
        
        text = "💳 کارت‌های پرداخت:\n\n"
        for card in payment_cards:
            primary_mark = "⭐ " if card.is_primary else ""
            text += f"{primary_mark}💳 {card.holder_name}\n"
            text += f"   🏦 {card.card_number}\n"
            if card.bank_name:
                text += f"   🏛️ {card.bank_name}\n"
            text += "\n"
        
        await message.answer(text)


@router.message(F.text == "🔙 بازگشت به منوی اصلی")
async def back_to_main_menu(message: Message):
    from bot.keyboards import main_menu_kb
    await message.answer("🔙 بازگشت به منوی اصلی", reply_markup=main_menu_kb())

