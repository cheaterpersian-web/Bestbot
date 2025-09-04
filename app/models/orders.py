from typing import Optional

from sqlalchemy import Integer, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PurchaseIntent(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("server.id"))
    amount_total: Mapped[float] = mapped_column(Numeric(18, 2))
    amount_paid_wallet: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    amount_due_receipt: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | paid | cancelled
    receipt_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)

