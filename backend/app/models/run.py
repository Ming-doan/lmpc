from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run_configs.id"), nullable=False
    )
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id")
    )
    iteration: Mapped[int] = mapped_column(Integer, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    priority: Mapped[int] = mapped_column(Integer, server_default="0")
    attempt: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="3")

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    image_digest: Mapped[str | None] = mapped_column(String(128))
    platform_version: Mapped[str | None] = mapped_column(String(50))
    resolved_args: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    worker_specs_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    container_id: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    config: Mapped["RunConfig"] = relationship(back_populates="runs")  # noqa: F821
    worker: Mapped["Worker | None"] = relationship(back_populates="runs")  # noqa: F821
    result: Mapped["BenchmarkResult | None"] = relationship(back_populates="run")  # noqa: F821
    traces: Mapped[list["RequestTrace"]] = relationship(back_populates="run")  # noqa: F821
    metric_samples: Mapped[list["MetricSample"]] = relationship(back_populates="run")  # noqa: F821

    __table_args__ = (
        Index("idx_queue_pickup", "status", "priority", "queued_at"),
        Index("ix_benchmark_runs_worker_status", "worker_id", "status"),
        Index("ix_benchmark_runs_config_id", "config_id"),
    )


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmark_runs.id"), primary_key=True
    )

    ttft_p50: Mapped[float | None] = mapped_column()
    ttft_p90: Mapped[float | None] = mapped_column()
    ttft_p95: Mapped[float | None] = mapped_column()
    ttft_p99: Mapped[float | None] = mapped_column()
    ttft_mean: Mapped[float | None] = mapped_column()
    ttft_stddev: Mapped[float | None] = mapped_column()

    tpot_p50: Mapped[float | None] = mapped_column()
    tpot_p99: Mapped[float | None] = mapped_column()
    tpot_mean: Mapped[float | None] = mapped_column()

    e2e_p50: Mapped[float | None] = mapped_column()
    e2e_p99: Mapped[float | None] = mapped_column()
    e2e_mean: Mapped[float | None] = mapped_column()

    output_tps_mean: Mapped[float | None] = mapped_column()
    output_tps_per_user: Mapped[float | None] = mapped_column()
    total_tps_mean: Mapped[float | None] = mapped_column()
    requests_per_sec: Mapped[float | None] = mapped_column()
    goodput_rps: Mapped[float | None] = mapped_column()

    total_requests: Mapped[int | None] = mapped_column(Integer)
    successful_requests: Mapped[int | None] = mapped_column(Integer)
    failed_requests: Mapped[int | None] = mapped_column(Integer)
    total_input_tokens: Mapped[int | None] = mapped_column()
    total_output_tokens: Mapped[int | None] = mapped_column()

    peak_gpu_mem_mb: Mapped[int | None] = mapped_column(Integer)
    avg_gpu_util_pct: Mapped[float | None] = mapped_column()
    peak_gpu_util_pct: Mapped[float | None] = mapped_column()
    peak_ram_mb: Mapped[int | None] = mapped_column(Integer)
    avg_cpu_pct: Mapped[float | None] = mapped_column()
    avg_power_watts: Mapped[float | None] = mapped_column()
    energy_joules: Mapped[float | None] = mapped_column()

    container_start_ms: Mapped[int | None] = mapped_column(Integer)
    model_load_ms: Mapped[int | None] = mapped_column(Integer)
    first_ready_ms: Mapped[int | None] = mapped_column(Integer)

    tokens_per_joule: Mapped[float | None] = mapped_column()
    tokens_per_gb_vram: Mapped[float | None] = mapped_column()

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    run: Mapped["BenchmarkRun"] = relationship(back_populates="result")


class RequestTrace(Base):
    __tablename__ = "request_traces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmark_runs.id"), nullable=False
    )
    request_idx: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ttft_ms: Mapped[float | None] = mapped_column()
    tpot_ms: Mapped[float | None] = mapped_column()
    e2e_ms: Mapped[float | None] = mapped_column()
    queue_wait_ms: Mapped[float | None] = mapped_column()
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool | None] = mapped_column()
    http_status: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    run: Mapped["BenchmarkRun"] = relationship(back_populates="traces")

    __table_args__ = (
        Index("ix_request_traces_run_started", "run_id", "started_at"),
        Index("ix_request_traces_started_at", "started_at"),
    )


class MetricSample(Base):
    __tablename__ = "metric_samples"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmark_runs.id"), nullable=False, primary_key=True
    )
    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id"), nullable=False
    )

    cpu_pct: Mapped[float | None] = mapped_column()
    ram_used_mb: Mapped[int | None] = mapped_column(Integer)
    ram_pct: Mapped[float | None] = mapped_column()

    gpu_index: Mapped[int | None] = mapped_column(Integer, server_default="0")
    gpu_util_pct: Mapped[int | None] = mapped_column(Integer)
    gpu_mem_used_mb: Mapped[int | None] = mapped_column(Integer)
    gpu_mem_total_mb: Mapped[int | None] = mapped_column(Integer)
    gpu_temp_c: Mapped[int | None] = mapped_column(Integer)
    gpu_power_watts: Mapped[float | None] = mapped_column()
    gpu_sm_clock_mhz: Mapped[int | None] = mapped_column(Integer)

    disk_read_mbps: Mapped[float | None] = mapped_column()
    disk_write_mbps: Mapped[float | None] = mapped_column()
    net_rx_mbps: Mapped[float | None] = mapped_column()
    net_tx_mbps: Mapped[float | None] = mapped_column()

    run: Mapped["BenchmarkRun"] = relationship(back_populates="metric_samples")

    __table_args__ = (
        Index("ix_metric_samples_run_time", "run_id", "time"),
        Index("ix_metric_samples_worker_time", "worker_id", "time"),
    )


