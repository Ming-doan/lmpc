import uuid
import sqlalchemy as sa
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Boolean, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.db import Base

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_source: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hardware: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workers.id"), nullable=True)
    inference_container_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inference_endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avg_latency_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    avg_throughput_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    avg_ttft_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    avg_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class BenchmarkStep(Base):
    __tablename__ = "benchmark_steps"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String, nullable=False)
    step_status: Mapped[str] = mapped_column(String, nullable=False)
    progress_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class BenchmarkMetricSnapshot(Base):
    __tablename__ = "benchmark_metric_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    t_offset_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    concurrency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    throughput_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ttft_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    cpu_pct: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    gpu_pct: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ram_mb: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    vram_mb: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)

class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"
    __table_args__ = (sa.UniqueConstraint("run_id", "concurrency"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_total: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_success: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    ttft_ms_p50: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ttft_ms_p95: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ttft_ms_p99: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tpot_ms_p50: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tpot_ms_p95: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tpot_ms_p99: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    throughput_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    per_req_tps_p50: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    input_tokens_avg: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    output_tokens_avg: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    duration_s: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
