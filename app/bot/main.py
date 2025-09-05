import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

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
from .middlewares.last_seen import LastSeenMiddleware
from .routers import configs as configs_router
from .routers import account as account_router
from .routers import admin_manage as admin_manage_router
from .routers import tutorials as tutorials_router
from .routers import tickets as tickets_router
from .routers import other as other_router
from .routers import lookup as lookup_router
from .routers import referrals as referrals_router
from .routers import discounts as discounts_router
from .routers import resellers as resellers_router
from .routers import payment_gateways as payment_gateways_router
from .routers import trial_system as trial_system_router
from .routers import smart_discounts as smart_discounts_router
from .routers import crm as crm_router
from .routers import backup as backup_router
from .routers import notifications as notifications_router
from .routers import advanced_reseller as advanced_reseller_router
from .routers import anti_fraud as anti_fraud_router
from .routers import financial_reports as financial_reports_router
from .routers import scheduled_messages as scheduled_messages_router
from .routers import refund_system as refund_system_router


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    # Register or update user
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == message.from_user.id))
        user = result.scalar_one_or_none()
        payload = ""
        try:
            if message.text and " " in message.text:
                payload = message.text.split(" ", 1)[1].strip()
        except Exception:
            payload = ""
        if user is None:
            user = TelegramUser(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                is_admin=message.from_user.id in set(settings.admin_ids),
                referral_code=str(message.from_user.id),
            )
            # handle referral deep-link
            if payload:
                ref_id = None
                if payload.isdigit():
                    ref_id = int(payload)
                elif payload.lower().startswith("ref_") and payload[4:].isdigit():
                    ref_id = int(payload[4:])
                elif payload.lower().startswith("u") and payload[1:].isdigit():
                    ref_id = int(payload[1:])
                if ref_id and ref_id != message.from_user.id:
                    # find referrer by telegram_user_id or internal id match
                    ref_user = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == ref_id))).scalar_one_or_none()
                    if ref_user:
                        user.referred_by_user_id = ref_user.id
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


@router.message(F.text.in_(set()))
async def placeholder_menu_handler(message: Message):
    await message.answer("این بخش به‌زودی فعال می‌شود.")


async def main() -> None:
    # Debug log sanitized token last 4 chars
    try:
        tail = settings.bot_token[-4:] if settings.bot_token else ""
        print(f"[bot] bot_token present: {'yes' if settings.bot_token else 'no'} tail=****{tail}")
    except Exception:
        pass

    if not settings.bot_token or settings.bot_token == "your_telegram_bot_token_here":
        print("BOT_TOKEN تنظیم نشده است. لطفاً مقدار صحیح را در فایل .env قرار دهید.")
        return

    await init_db_schema()

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(BlockMiddleware())
    dp.message.middleware(LastSeenMiddleware())
    dp.include_router(router)
    dp.include_router(user_main.router)
    dp.include_router(wallet_router.router)
    dp.include_router(buy_router.router)
    dp.include_router(util_router.router)
    dp.include_router(admin_router.router)
    dp.include_router(configs_router.router)
    dp.include_router(account_router.router)
    dp.include_router(admin_manage_router.router)
    dp.include_router(tutorials_router.router)
    dp.include_router(tickets_router.router)
    dp.include_router(other_router.router)
    dp.include_router(lookup_router.router)
    dp.include_router(referrals_router.router)
    dp.include_router(discounts_router.router)
    dp.include_router(resellers_router.router)
    dp.include_router(payment_gateways_router.router)
    dp.include_router(trial_system_router.router)
    dp.include_router(smart_discounts_router.router)
    dp.include_router(crm_router.router)
    dp.include_router(backup_router.router)
    dp.include_router(notifications_router.router)
    dp.include_router(advanced_reseller_router.router)
    dp.include_router(anti_fraud_router.router)
    dp.include_router(financial_reports_router.router)
    dp.include_router(scheduled_messages_router.router)
    dp.include_router(refund_system_router.router)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), stream=sys.stdout)
    asyncio.run(main())

