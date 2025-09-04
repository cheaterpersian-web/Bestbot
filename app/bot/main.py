import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from core.config import settings
from core.db import init_db_schema, get_db_session
from models.user import TelegramUser

from .keyboards import main_menu_kb
from .routers import user_main
from .routers import wallet as wallet_router
from .routers import buy as buy_router
from .middlewares.block import BlockMiddleware
from .routers import admin as admin_router
from .routers import util as util_router


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    # Register or update user
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                is_admin=message.from_user.id in set(settings.admin_ids),
            )
            session.add(user)
        else:
            user.username = message.from_user.username
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name

    text = (
        "سلام! به ربات فروش VPN خوش آمدید.\n\n"
        "از منوی زیر یکی از گزینه‌ها را انتخاب کنید."
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.message(F.text.in_({
    "کانفیگ‌های من",
    "حساب کاربری",
    "دعوت دوستان",
    "تیکت‌ها",
    "آموزش اتصال",
    "استعلام کانفیگ",
    "سایر امکانات",
}))
async def placeholder_menu_handler(message: Message):
    await message.answer("این بخش به‌زودی فعال می‌شود.")


async def main() -> None:
    if not settings.bot_token or settings.bot_token == "your_telegram_bot_token_here":
        print("BOT_TOKEN تنظیم نشده است. لطفاً مقدار صحیح را در فایل .env قرار دهید.")
        return

    await init_db_schema()

    dp = Dispatcher()
    dp.message.middleware(BlockMiddleware())
    dp.include_router(router)
    dp.include_router(user_main.router)
    dp.include_router(wallet_router.router)
    dp.include_router(buy_router.router)
    dp.include_router(util_router.router)
    dp.include_router(admin_router.router)

    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), stream=sys.stdout)
    asyncio.run(main())

