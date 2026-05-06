from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    adapter_class: Mapped[str | None] = mapped_column(String(100))
    default_image: Mapped[str | None] = mapped_column(String(255))
    default_port: Mapped[int | None] = mapped_column(Integer)
    default_args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)

    configs: Mapped[list["RunConfig"]] = relationship(back_populates="platform")  # noqa: F821
