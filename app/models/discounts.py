from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DiscountCode(Base):
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    percent_off: Mapped[int] = mapped_column(Integer, default=0)
    fixed_off: Mapped[int] = mapped_column(Integer, default=0)
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    apply_on_wallet: Mapped[bool] = mapped_column(Boolean, default=False)
    apply_on_purchase: Mapped[bool] = mapped_column(Boolean, default=True)
    apply_on_renewal: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

