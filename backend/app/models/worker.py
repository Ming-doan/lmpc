from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Boolean, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    api_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    specs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    capabilities: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    runs: Mapped[list["BenchmarkRun"]] = relationship(back_populates="worker")  # noqa: F821

    __table_args__ = (
        Index("ix_workers_status", "status"),
        Index("ix_workers_last_heartbeat_at", "last_heartbeat_at"),
    )
