from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Server(Base):
    name: Mapped[str] = mapped_column(String(64), unique=True)
    api_base_url: Mapped[str] = mapped_column(String(256))
    api_key: Mapped[str] = mapped_column(String(256))
    panel_type: Mapped[str] = mapped_column(String(16), default="mock")  # mock | xui | 3xui | hiddify
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    capacity_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # optional capacity tracking


class Category(Base):
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Plan(Base):
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("server.id"))
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    price_irr: Mapped[float] = mapped_column(Numeric(18, 2))
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    traffic_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

