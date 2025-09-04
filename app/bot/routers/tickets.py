from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from core.config import settings
from core.db import get_db_session
from models.support import Ticket, TicketMessage
from models.user import TelegramUser


router = Router(name="tickets")


class TicketStates(StatesGroup):
    waiting_subject = State()
    waiting_body = State()


@router.message(F.text == "تیکت‌ها")
async def tickets_menu(message: Message, state: FSMContext):
    await message.answer("برای ارسال تیکت جدید، عنوان تیکت را ارسال کنید.")
    await state.set_state(TicketStates.waiting_subject)


@router.message(TicketStates.waiting_subject)
async def create_ticket_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text.strip())
    await message.answer("متن تیکت را ارسال کنید.")
    await state.set_state(TicketStates.waiting_body)


@router.message(TicketStates.waiting_body)
async def create_ticket_body(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
        t = Ticket(user_id=me.id, subject=subject, status="open")
        session.add(t)
        await session.flush()
        tm = TicketMessage(ticket_id=t.id, sender_user_id=me.id, body=message.text.strip(), by_admin=False)
        session.add(tm)

    await message.answer("تیکت شما ثبت شد. پشتیبانی پاسخ خواهد داد.")
    await state.clear()

    # notify admins
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(chat_id=admin_id, text=f"تیکت جدید: {subject}")
        except Exception:
            pass

