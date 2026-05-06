from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateRunsRequest(BaseModel):
    config_id: uuid.UUID
    iterations: int = 1
    priority: int = 0


class ConfigSummary(BaseModel):
    id: uuid.UUID
    name: str
    platform_name: str | None = None
    model_name: str | None = None

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    worker_id: uuid.UUID | None
    iteration: int
    status: str
    priority: int
    attempt: int
    queued_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    image_digest: str | None
    platform_version: str | None
    error_code: str | None
    error_message: str | None
    config: ConfigSummary | None = None

    model_config = {"from_attributes": True}


class ResultsSubmission(BaseModel):
    aggregates: dict[str, Any]
    request_traces: list[dict[str, Any]] = []
    metric_samples: list[dict[str, Any]] = []


class BenchmarkResultOut(BaseModel):
    run_id: uuid.UUID
    ttft_p50: float | None = None
    ttft_p90: float | None = None
    ttft_p95: float | None = None
    ttft_p99: float | None = None
    ttft_mean: float | None = None
    ttft_stddev: float | None = None
    tpot_p50: float | None = None
    tpot_p90: float | None = None
    tpot_p95: float | None = None
    tpot_p99: float | None = None
    tpot_mean: float | None = None
    tpot_stddev: float | None = None
    e2e_p50: float | None = None
    e2e_p90: float | None = None
    e2e_p95: float | None = None
    e2e_p99: float | None = None
    e2e_mean: float | None = None
    e2e_stddev: float | None = None
    output_tps_mean: float | None = None
    output_tps_per_user: float | None = None
    total_tps_mean: float | None = None
    requests_per_sec: float | None = None
    goodput_rps: float | None = None
    total_requests: int | None = None
    successful_requests: int | None = None
    failed_requests: int | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    peak_gpu_mem_mb: int | None = None
    avg_gpu_util_pct: float | None = None
    peak_gpu_util_pct: float | None = None
    peak_ram_mb: int | None = None
    avg_cpu_pct: float | None = None
    avg_power_watts: float | None = None
    energy_joules: float | None = None
    container_start_ms: float | None = None
    model_load_ms: float | None = None
    first_ready_ms: float | None = None
    tokens_per_joule: float | None = None
    tokens_per_gb_vram: float | None = None
    computed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RequestTraceOut(BaseModel):
    id: int
    run_id: uuid.UUID
    request_idx: int | None
    started_at: datetime
    ttft_ms: float | None
    tpot_ms: float | None
    e2e_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    success: bool | None
    http_status: int | None
    error: str | None

    model_config = {"from_attributes": True}


class MetricSampleOut(BaseModel):
    time: datetime
    run_id: uuid.UUID
    cpu_pct: float | None
    ram_used_mb: int | None
    gpu_util_pct: int | None
    gpu_mem_used_mb: int | None
    gpu_power_watts: float | None

    model_config = {"from_attributes": True}
