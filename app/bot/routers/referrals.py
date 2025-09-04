from aiogram import Router, F
from aiogram.types import Message

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser
from models.content import ContentItem


router = Router(name="referrals")


@router.message(F.text == "دعوت دوستان")
async def referrals_menu(message: Message):
    async with get_db_session() as session:
        from sqlalchemy import select
        me = (
            await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        ).scalar_one()
        ref_text = (
            await session.execute(select(ContentItem).where(ContentItem.key == "ref_text"))
        ).scalar_one_or_none()
        banner = (
            await session.execute(select(ContentItem).where(ContentItem.key == "ref_banner_file_id"))
        ).scalar_one_or_none()

    if not settings.bot_username:
        link_line = "لطفاً bot_username را در تنظیمات قرار دهید."
    else:
        link = f"https://t.me/{settings.bot_username}?start={me.telegram_user_id}"
        link_line = f"لینک دعوت اختصاصی شما:\n{link}"

    text = (ref_text.text if (ref_text and ref_text.text) else "دوستان‌تان را دعوت کنید و هدیه بگیرید!")
    caption = f"{text}\n\n{link_line}"
    if banner and banner.file_id:
        try:
            await message.answer_photo(photo=banner.file_id, caption=caption)
            return
        except Exception:
            pass
    await message.answer(caption)

