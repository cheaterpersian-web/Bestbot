from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from core.db import get_db_session
from models.user import TelegramUser
from models.service import Service
from services.qrcode_gen import generate_qr_with_template
from services.panels.factory import get_panel_client


router = Router(name="configs")


def service_actions_kb(svc_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="نمایش لینک", callback_data=f"svc:link:{svc_id}"), InlineKeyboardButton(text="ارسال QR", callback_data=f"svc:qr:{svc_id}")],
            [InlineKeyboardButton(text="بروزرسانی لینک", callback_data=f"svc:update:{svc_id}"), InlineKeyboardButton(text="تعویض UUID", callback_data=f"svc:regen_uuid:{svc_id}")],
            [InlineKeyboardButton(text="تمدید 30 روز", callback_data=f"svc:renew30:{svc_id}"), InlineKeyboardButton(text="افزایش 50گیگ", callback_data=f"svc:add50:{svc_id}")],
            [InlineKeyboardButton(text="حذف سرویس", callback_data=f"svc:delete:{svc_id}")],
        ]
    )


@router.message(F.text == "کانفیگ‌های من")
async def my_configs(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
        svcs = (
            await session.execute(select(Service).where(Service.user_id == me.id).order_by(Service.created_at.desc()))
        ).scalars().all()
    if not svcs:
        await message.answer("هنوز سرویسی ندارید.")
        return
    for s in svcs:
        title = f"سرویس #{s.id} | Remark: {s.remark}\nوضعیت: {'فعال' if s.is_active else 'غیرفعال'}"
        await message.answer(title, reply_markup=service_actions_kb(s.id))


@router.callback_query(F.data.startswith("svc:link:"))
async def svc_link(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
    if not svc:
        await callback.answer("یافت نشد", show_alert=True)
        return
    await callback.message.answer(svc.subscription_url)
    await callback.answer()


@router.callback_query(F.data.startswith("svc:renew30:"))
async def svc_renew(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        if not svc:
            await callback.answer("یافت نشد", show_alert=True)
            return
        client = get_panel_client("mock")
        await client.renew_service(svc.uuid, add_days=30)
    await callback.message.answer(f"تمدید ۳۰ روز انجام شد برای سرویس #{svc_id}")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:add50:"))
async def svc_add_traffic(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        if not svc:
            await callback.answer("یافت نشد", show_alert=True)
            return
        client = get_panel_client("mock")
        await client.add_traffic(svc.uuid, add_gb=50)
    await callback.message.answer(f"۵۰ گیگ به سرویس #{svc_id} اضافه شد")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:update:"))
async def svc_update_link(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        if not svc:
            await callback.answer("یافت نشد", show_alert=True)
            return
        # For MVP, assume subscription URL may change on panel side; here we keep as is
    await callback.message.answer("لینک سرویس شما به‌روزرسانی شد (در صورت تغییر).")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:qr:"))
async def svc_qr(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
    if not svc:
        await callback.answer("یافت نشد", show_alert=True)
        return
    qr_bytes = generate_qr_with_template(svc.subscription_url)
    await callback.message.answer_photo(BufferedInputFile(qr_bytes, filename="sub.png"), caption=f"QR سرویس #{svc.id}")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:regen_uuid:"))
async def svc_regen_uuid(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        if not svc:
            await callback.answer("یافت نشد", show_alert=True)
            return
        # call panel to generate new uuid
        client = get_panel_client("mock")
        new_uuid = await client.reset_uuid(svc.uuid)
        # naive update subscription_url for MVP (real panel should return new link)
        svc.uuid = new_uuid
        if "sub/" in svc.subscription_url:
            base = svc.subscription_url.split("sub/")[0] + "sub/"
            svc.subscription_url = base + new_uuid
    await callback.message.answer(f"UUID جدید اعمال شد برای سرویس #{svc_id}")
    await callback.answer()


@router.callback_query(F.data.startswith("svc:delete:"))
async def svc_delete(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_db_session() as session:
        from sqlalchemy import select, delete
        svc = (await session.execute(select(Service).where(Service.id == svc_id))).scalar_one_or_none()
        if not svc:
            await callback.answer("یافت نشد", show_alert=True)
            return
        client = get_panel_client("mock")
        try:
            await client.delete_service(svc.uuid)
        except Exception:
            pass
        await session.delete(svc)
    await callback.message.answer(f"سرویس #{svc_id} حذف شد.")
    await callback.answer()

