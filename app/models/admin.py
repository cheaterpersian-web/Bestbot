from typing import Optional
from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AdminUser(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    role: Mapped[str] = mapped_column(String(32), default="admin")  # admin | super_admin | support
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string of permissions
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)


class BotSettings(Base):
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    data_type: Mapped[str] = mapped_column(String(16), default="string")  # string | int | float | bool | json


class Gift(Base):
    from_admin_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)  # None for bulk
    type: Mapped[str] = mapped_column(String(32))  # wallet_balance | traffic_gb | time_days
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_bulk: Mapped[bool] = mapped_column(Boolean, default=False)
    target_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON criteria for bulk gifts
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | processing | completed | failed


class ResellerRequest(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | approved | rejected | blacklisted
    requested_discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    approved_discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    business_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    reviewed_by_admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Reseller(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_reseller_id: Mapped[Optional[int]] = mapped_column(ForeignKey("reseller.id"), nullable=True)  # Multi-level support
    commission_percent: Mapped[int] = mapped_column(Integer, default=0)
    total_sales: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_commission: Mapped[float] = mapped_column(Numeric(18, 2), default=0)


class Button(Base):
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(16))  # link | text | image
    content: Mapped[str] = mapped_column(Text)  # URL, text content, or file_id
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)