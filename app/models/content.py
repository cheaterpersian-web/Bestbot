from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ContentItem(Base):
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

