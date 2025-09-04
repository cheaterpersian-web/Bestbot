from typing import Callable, Awaitable, Dict, Any
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from core.db import get_db_session
from models.user import TelegramUser


class LastSeenMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
        if user_id:
            async with get_db_session() as session:
                from sqlalchemy import select
                db_user = (
                    await session.execute(
                        select(TelegramUser).where(TelegramUser.telegram_user_id == user_id)
                    )
                ).scalar_one_or_none()
                if db_user:
                    db_user.last_seen_at = datetime.utcnow()
        return await handler(event, data)

