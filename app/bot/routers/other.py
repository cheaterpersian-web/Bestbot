from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.db import get_db_session
from models.content import ContentItem


router = Router(name="other")


def other_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="لیست قیمت", callback_data="other:prices")],
            [InlineKeyboardButton(text="سوالات متداول (FAQ)", callback_data="other:faq")],
            [InlineKeyboardButton(text="وضعیت سرویس", callback_data="other:status")],
            [InlineKeyboardButton(text="درخواست نمایندگی", callback_data="other:reseller")],
            [InlineKeyboardButton(text="درخواست تست رایگان", callback_data="other:trial")],
        ]
    )


@router.message(F.text == "سایر امکانات")
async def other_menu(message: Message):
    await message.answer("سایر امکانات:", reply_markup=other_menu_kb())


@router.callback_query(F.data == "other:prices")
async def other_prices(callback):
    async with get_db_session() as session:
        from sqlalchemy import select
        item = (await session.execute(select(ContentItem).where(ContentItem.key == "price_list_text"))).scalar_one_or_none()
    if item and item.text:
        await callback.message.answer(item.text)
    else:
        await callback.message.answer("لیست قیمت ثبت نشده است. لطفاً با پشتیبانی تماس بگیرید.")
    await callback.answer()


@router.callback_query(F.data == "other:faq")
async def other_faq(callback):
    async with get_db_session() as session:
        from sqlalchemy import select
        item = (await session.execute(select(ContentItem).where(ContentItem.key == "faq_text"))).scalar_one_or_none()
    if item and item.text:
        await callback.message.answer(item.text)
    else:
        await callback.message.answer("FAQ ثبت نشده است.")
    await callback.answer()


@router.callback_query(F.data == "other:status")
async def other_status(callback):
    async with get_db_session() as session:
        from sqlalchemy import select
        item = (await session.execute(select(ContentItem).where(ContentItem.key == "status_url"))).scalar_one_or_none()
    url = (item.text if item and item.text else settings.status_url or "")
    if url:
        await callback.message.answer(f"وضعیت سرویس: {url}")
    else:
        await callback.message.answer("لینک وضعیت تنظیم نشده است.")
    await callback.answer()


@router.callback_query(F.data == "other:reseller")
async def other_reseller(callback):
    await callback.message.answer("درخواست شما ثبت شد. بررسی و به شما اطلاع داده می‌شود.")
    # notify admins
    for admin_id in settings.admin_ids:
        try:
            await callback.message.bot.send_message(chat_id=admin_id, text=f"درخواست نمایندگی جدید از کاربر {callback.from_user.id}")
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data == "other:trial")
async def other_trial(callback):
    await callback.message.answer("درخواست تست شما ثبت شد. لطفاً در صورت نیاز مدارک را ارسال کنید.")
    for admin_id in settings.admin_ids:
        try:
            await callback.message.bot.send_message(chat_id=admin_id, text=f"درخواست تست رایگان از کاربر {callback.from_user.id}")
        except Exception:
            pass
    await callback.answer()

