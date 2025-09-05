from typing import Optional
from datetime import datetime

from sqlalchemy import BigInteger, String, Boolean, Numeric, ForeignKey, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TelegramUser(Base):
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    wallet_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    last_seen_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    referred_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    referral_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    total_spent: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_services: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_source: Mapped[str] = mapped_column(String(32), default="bot")  # bot | web | api
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

