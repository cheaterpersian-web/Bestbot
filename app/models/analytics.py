from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserActivity(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    action: Mapped[str] = mapped_column(String(64))  # login | purchase | wallet_topup | config_use | etc.
    details: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class DailyStats(Base):
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    total_services: Mapped[int] = mapped_column(Integer, default=0)
    new_services: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    wallet_topups: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0)


class ServiceUsage(Base):
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id"))
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    traffic_used_gb: Mapped[float] = mapped_column(Numeric(10, 3), default=0)
    connection_count: Mapped[int] = mapped_column(Integer, default=0)
    last_connection_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)