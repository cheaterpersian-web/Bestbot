from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Service(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("server.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    remark: Mapped[str] = mapped_column(String(128))
    uuid: Mapped[str] = mapped_column(String(64), index=True)
    subscription_url: Mapped[str] = mapped_column(String(1024))
    qr_image_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    traffic_used_gb: Mapped[float] = mapped_column(Numeric(10, 3), default=0)
    traffic_limit_gb: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    renewal_count: Mapped[int] = mapped_column(Integer, default=0)

