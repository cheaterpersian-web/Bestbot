from datetime import datetime
from typing import Optional

from sqlalchemy import String, Numeric, Integer, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PaymentCard(Base):
    holder_name: Mapped[str] = mapped_column(String(128))
    card_last4: Mapped[str] = mapped_column(String(4))
    card_number: Mapped[str] = mapped_column(String(19))  # Full card number for processing
    bank_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Transaction(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(8), default="IRR")
    type: Mapped[str] = mapped_column(String(32))  # wallet_topup | purchase | refund | transfer | gift
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | approved | rejected
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    receipt_image_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    approved_by_admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("telegramuser.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejected_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bonus_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    discount_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    related_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaction.id"), nullable=True)
    payment_gateway: Mapped[str] = mapped_column(String(32), default="card_to_card")  # card_to_card | stars | zarinpal
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    fraud_score: Mapped[float] = mapped_column(Numeric(3, 2), default=0)  # 0-1 fraud probability

