from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.admin import BotSettings
from core.config import settings as env_settings


async def get_str(session: AsyncSession, key: str, default: Optional[str] = None) -> Optional[str]:
    row = (await session.execute(select(BotSettings).where(BotSettings.key == key))).scalar_one_or_none()
    return row.value if row else default


async def get_bool(session: AsyncSession, key: str, default: bool) -> bool:
    row = (await session.execute(select(BotSettings).where(BotSettings.key == key))).scalar_one_or_none()
    if not row:
        return bool(default)
    val = (row.value or "").strip().lower()
    return val in {"1", "true", "yes", "on", "enabled"}


async def get_int(session: AsyncSession, key: str, default: int) -> int:
    row = (await session.execute(select(BotSettings).where(BotSettings.key == key))).scalar_one_or_none()
    if not row or row.value is None or row.value == "":
        return int(default)
    try:
        return int(float(row.value))
    except Exception:
        return int(default)


async def get_payment_methods(session: AsyncSession) -> list[str]:
    """Return enabled payment methods in the configured order.
    Supported keys: wallet, card, stars, zarinpal
    """
    order = (await get_str(session, "payment_methods_order", "wallet,card,stars,zarinpal")) or "wallet,card,stars,zarinpal"
    enabled = {
        "wallet": await get_bool(session, "enable_wallet_payment", True),
        "card": await get_bool(session, "enable_card_to_card", True),
        "stars": await get_bool(session, "enable_stars", bool(getattr(env_settings, "enable_stars", False))),
        "zarinpal": await get_bool(session, "enable_zarinpal", bool(getattr(env_settings, "enable_zarinpal", False))),
    }
    methods: list[str] = []
    for m in [m.strip() for m in order.split(",") if m.strip()]:
        if enabled.get(m):
            methods.append(m)
    # Ensure at least one fallback
    if not methods:
        # try wallet then card
        if enabled.get("wallet"):
            methods.append("wallet")
        elif enabled.get("card"):
            methods.append("card")
    return methods


async def get_effective_flag(session: AsyncSession, key: str, env_default_attr: str, default_value: bool) -> bool:
    """Get boolean flag prioritizing DB setting then env settings fallback."""
    row = (await session.execute(select(BotSettings).where(BotSettings.key == key))).scalar_one_or_none()
    if row:
        val = (row.value or "").strip().lower()
        return val in {"1", "true", "yes", "on", "enabled"}
    return bool(getattr(env_settings, env_default_attr, default_value))

