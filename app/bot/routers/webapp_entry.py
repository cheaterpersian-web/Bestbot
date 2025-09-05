from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from core.config import settings


router = Router()


def _webapp_kb() -> InlineKeyboardMarkup:
    url = settings.webapp_url
    buttons = []
    if url:
        buttons.append([InlineKeyboardButton(text="🖥️ پنل کاربری", web_app=WebAppInfo(url=url))])
    return InlineKeyboardMarkup(inline_keyboard=buttons or [[InlineKeyboardButton(text="وب‌اپ تنظیم نشده", url="https://t.me/BotFather")]])


@router.message(Command(commands=["app", "webapp"]))
async def open_webapp_command(message: Message):
    await message.answer("برای باز کردن پنل کاربری روی دکمه زیر بزنید:", reply_markup=_webapp_kb())


@router.message(F.text.lower().in_({"پنل کاربری", "وب اپ", "webapp", "app"}))
async def open_webapp_text(message: Message):
    await message.answer("برای باز کردن پنل کاربری روی دکمه زیر بزنید:", reply_markup=_webapp_kb())

