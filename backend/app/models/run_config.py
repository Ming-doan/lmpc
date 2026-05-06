from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RunConfig(Base):
    __tablename__ = "run_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id"), nullable=False)
    prompt_set_id: Mapped[int] = mapped_column(ForeignKey("prompt_sets.id"), nullable=False)
    platform_args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    benchmark_args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    platform: Mapped["Platform"] = relationship(back_populates="configs")  # noqa: F821
    model: Mapped["Model"] = relationship(back_populates="configs")  # noqa: F821
    prompt_set: Mapped["PromptSet"] = relationship(back_populates="configs")  # noqa: F821
    runs: Mapped[list["BenchmarkRun"]] = relationship(back_populates="config")  # noqa: F821
