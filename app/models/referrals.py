from sqlalchemy import String, Integer, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ReferralEvent(Base):
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    buyer_user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    bonus_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    description: Mapped[str] = mapped_column(String(256))

