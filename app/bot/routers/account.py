from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from core.db import get_db_session
from models.user import TelegramUser


router = Router(name="account")


class TransferStates(StatesGroup):
    waiting_target = State()
    waiting_amount = State()


@router.message(F.text == "حساب کاربری")
async def account_info(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
    await message.answer(
        f"آیدی: {me.telegram_user_id}\nیوزرنیم: @{me.username or '-'}\nموجودی کیف پول: {int(me.wallet_balance or 0):,}"
    )
    await message.answer("برای انتقال موجودی، آیدی عددی مقصد را ارسال کنید.")


@router.message(F.text.regexp(r"^انتقال موجودی$"))
async def start_transfer(message: Message, state: FSMContext):
    await message.answer("آیدی عددی مقصد را بفرستید.")
    await state.set_state(TransferStates.waiting_target)


@router.message(TransferStates.waiting_target, F.text.regexp(r"^\d+$"))
async def got_target(message: Message, state: FSMContext):
    await state.update_data(target_id=int(message.text))
    await message.answer("مبلغ انتقال (تومان) را وارد کنید.")
    await state.set_state(TransferStates.waiting_amount)


@router.message(TransferStates.waiting_amount, F.text.regexp(r"^\d+$"))
async def got_amount(message: Message, state: FSMContext):
    amount = int(message.text)
    data = await state.get_data()
    target_tg_id = data.get("target_id")

    async with get_db_session() as session:
        from sqlalchemy import select
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
        to_user = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == target_tg_id))
        ).scalar_one_or_none()
        if not to_user:
            await message.answer("کاربر مقصد یافت نشد.")
            await state.clear()
            return
        if (me.wallet_balance or 0) < amount:
            await message.answer("موجودی کافی نیست.")
            await state.clear()
            return
        me.wallet_balance = int(me.wallet_balance or 0) - amount
        to_user.wallet_balance = int(to_user.wallet_balance or 0) + amount

    await message.answer("انتقال انجام شد.")
    await state.clear()

