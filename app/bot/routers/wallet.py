from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove

from core.config import settings
from core.db import get_db_session
from models.billing import Transaction
from models.user import TelegramUser


router = Router(name="wallet")


class TopUpStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()


@router.message(F.text == "کیف پول / پرداخت‌ها")
async def wallet_menu(message: Message, state: FSMContext):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()
    await message.answer(
        f"موجودی کیف پول شما: {me.wallet_balance:.0f} تومان\n\nبرای شارژ کیف پول، مبلغ مورد نظر را ارسال کنید (تومان).\nحداقل: {settings.min_topup_amount:,} - حداکثر: {settings.max_topup_amount:,}",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(TopUpStates.waiting_for_amount)


@router.message(TopUpStates.waiting_for_amount, F.text.regexp(r"^\d+$"))
async def receive_amount(message: Message, state: FSMContext):
    amount = int(message.text)
    if amount < settings.min_topup_amount or amount > settings.max_topup_amount:
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
        tx = Transaction(
            user_id=me.id,
            amount=amount,
            type="wallet_topup",
            status="approved" if settings.auto_approve_receipts else "pending",
            description="Wallet top-up via receipt",
            receipt_image_file_id=file_id,
        )
        session.add(tx)
        if settings.auto_approve_receipts:
            me.wallet_balance = (me.wallet_balance or 0) + amount

    if settings.auto_approve_receipts:
        await message.answer(f"شارژ با موفقیت انجام شد. موجودی جدید: {amount:,} تومان افزوده شد.")
    else:
        await message.answer("رسید دریافت شد. پس از بررسی ادمین، نتیجه به شما اعلام می‌شود.")

    await state.clear()

