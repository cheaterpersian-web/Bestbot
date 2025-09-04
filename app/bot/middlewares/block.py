from typing import Callable, Awaitable, Dict, Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from core.db import get_db_session
from models.user import TelegramUser


class BlockMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: Dict[str, Any]) -> Any:
        if isinstance(event, Message) and event.from_user:
            async with get_db_session() as session:
                from sqlalchemy import select
                result = await session.execute(select(TelegramUser).where(TelegramUser.telegram_user_id == event.from_user.id))
                user = result.scalar_one_or_none()
                if user and user.is_blocked:
                    await event.answer("دسترسی شما به ربات مسدود شده است.")
                    return
        return await handler(event, data)

