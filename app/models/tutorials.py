from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Tutorial(Base):
    os_key: Mapped[str] = mapped_column(String(32), index=True)  # android | ios | windows | macos | linux
    title: Mapped[str] = mapped_column(String(128))
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

