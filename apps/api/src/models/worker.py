from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.db import Base

class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    secret_hash: Mapped[str] = mapped_column(String, nullable=False)
    gpu_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gpu_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vram_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cpu: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ram_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String, nullable=False, default="online")
