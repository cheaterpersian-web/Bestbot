from __future__ import annotations

from typing import Tuple

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from services.bot_settings import get_bool, get_str


def build_join_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{channel_username.lstrip('@')}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 عضویت در کانال", url=url)],
            [InlineKeyboardButton(text="✅ عضو شدم - بررسی کن", callback_data="join:check")],
        ]
    )


async def is_join_required_and_missing(bot: Bot, session: AsyncSession, telegram_user_id: int) -> Tuple[bool, str]:
    """Return (missing, channel_username). missing=True means user must join and is not a member.
    If join requirement disabled or channel not set, returns (False, "").
    """
    required = await get_bool(session, "join_channel_required", False)
    if not required:
        return False, ""
    channel = await get_str(session, "join_channel_username", "") or ""
    if not channel:
        return False, ""
    channel = channel.lstrip('@')
    try:
        member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=telegram_user_id)
        status = getattr(member, "status", "left")
        if status in {"creator", "administrator", "member", "restricted"}:
            return False, channel
        return True, channel
    except Exception:
        # On error, assume not a member to be safe
        return True, channel

