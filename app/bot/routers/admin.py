from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from core.config import settings
from core.db import get_db_session
from models.user import TelegramUser


router = Router(name="admin")


def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="داشبورد"), KeyboardButton(text="بررسی رسیدها")],
            [KeyboardButton(text="مدیریت سرورها"), KeyboardButton(text="مدیریت دسته‌ها")],
            [KeyboardButton(text="مدیریت پلن‌ها"), KeyboardButton(text="پیام همگانی")],
        ],
        resize_keyboard=True,
        input_field_placeholder="یک گزینه ادمین را انتخاب کنید",
    )


async def _is_admin(telegram_id: int) -> bool:
    # runtime check: settings or DB flag
    if telegram_id in set(settings.admin_ids):
        return True
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        return bool(user and user.is_admin)


@router.message(Command("admin"))
async def admin_entry(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("پنل مدیریت:", reply_markup=admin_kb())


@router.message(lambda m: m.text in {"داشبورد", "بررسی رسیدها", "مدیریت سرورها", "مدیریت دسته‌ها", "مدیریت پلن‌ها", "پیام همگانی"})
async def admin_placeholders(message: Message):
    if not await _is_admin(message.from_user.id):
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("این بخش به‌زودی تکمیل می‌شود.")

