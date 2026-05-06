from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Model(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hf_id: Mapped[str | None] = mapped_column(String(255))
    size_b: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    quantization: Mapped[str | None] = mapped_column(String(30))
    context_length: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

    configs: Mapped[list["RunConfig"]] = relationship(back_populates="model")  # noqa: F821
