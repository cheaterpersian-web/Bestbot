from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from core.db import get_db_session
from models.service import Service
from models.user import TelegramUser
from core.config import settings
from bot.inline import request_add_service_kb, admin_approve_add_service_kb


router = Router(name="lookup")


class LookupStates(StatesGroup):
    waiting_query = State()


@router.message(F.text == "استعلام کانفیگ")
async def lookup_start(message: Message, state: FSMContext):
    await message.answer("UUID یا لینک کانفیگ را ارسال کنید.")
    await state.set_state(LookupStates.waiting_query)


@router.message(LookupStates.waiting_query)
async def lookup_query(message: Message, state: FSMContext):
    q = message.text.strip()
    uuid = None
    if "uuid=" in q:
        # naive extract
        try:
            uuid = q.split("uuid=")[-1].split("&")[0]
        except Exception:
            uuid = None
    elif "/sub/" in q:
        try:
            uuid = q.split("/sub/")[-1].split("?")[0]
        except Exception:
            uuid = None
    else:
        uuid = q if len(q) >= 8 else None

    if not uuid:
        await message.answer("ورودی نامعتبر است.")
        await state.clear()
        return

    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.uuid == uuid))).scalar_one_or_none()
        me = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))).scalar_one()

    if not svc:
        await message.answer("یافت نشد.")
        await state.clear()
        return

    owned = (svc.user_id == me.id)
    await message.answer(f"نتیجه: سرویس #{svc.id} بر روی کاربر {'شما' if owned else 'دیگری'} است.")
    if not owned:
        await message.answer("در صورت نیاز، می‌توانید درخواست افزودن به حساب خود را ارسال کنید.", reply_markup=request_add_service_kb(svc.id))
    await state.clear()


@router.callback_query(F.data.startswith("lookup:reqadd:"))
async def req_add(callback, state: FSMContext):
    svc_id = int(callback.data.split(":")[-1])
    # notify admins to approve adding this service to current user
    for admin_id in settings.admin_ids:
        try:
            await callback.message.bot.send_message(chat_id=admin_id, text=f"درخواست افزودن سرویس #{svc_id} به کاربر {callback.from_user.id}", reply_markup=admin_approve_add_service_kb(svc_id, callback.from_user.id))
        except Exception:
            pass
    await callback.message.answer("درخواست شما ارسال شد و پس از بررسی اعمال می‌شود.")
    await callback.answer()

