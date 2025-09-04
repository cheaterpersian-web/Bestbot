from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TrialRequest(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | approved | rejected | expired
    requested_duration_days: Mapped[int] = mapped_column(Integer, default=1)
    approved_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requested_traffic_gb: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    approved_traffic_gb: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service.id"), nullable=True)  # Created service if approved


class TrialConfig(Base):
    """Trial configuration settings"""
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_duration_days: Mapped[int] = mapped_column(Integer, default=3)
    max_traffic_gb: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    max_requests_per_user: Mapped[int] = mapped_column(Integer, default=1)
    max_requests_per_day: Mapped[int] = mapped_column(Integer, default=10)
    require_phone_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    server_id: Mapped[Optional[int]] = mapped_column(ForeignKey("server.id"), nullable=True)  # Default trial server
    plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("plan.id"), nullable=True)  # Default trial plan