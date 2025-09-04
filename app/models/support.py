from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Ticket(Base):
    user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | closed
    subject: Mapped[str] = mapped_column(String(128))


class TicketMessage(Base):
    ticket_id: Mapped[int] = mapped_column(ForeignKey("ticket.id"))
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("telegramuser.id"))
    body: Mapped[str] = mapped_column(String(2048))
    by_admin: Mapped[bool] = mapped_column(Boolean, default=False)

