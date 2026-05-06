from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateRunsRequest(BaseModel):
    config_id: uuid.UUID
    iterations: int = 1
    priority: int = 0


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

    model_config = {"from_attributes": True}


class ResultsSubmission(BaseModel):
    aggregates: dict[str, Any]
    request_traces: list[dict[str, Any]] = []
    metric_samples: list[dict[str, Any]] = []


class BenchmarkResultOut(BaseModel):
    run_id: uuid.UUID
    ttft_p50: float | None
    ttft_p90: float | None
    ttft_p95: float | None
    ttft_p99: float | None
    ttft_mean: float | None
    ttft_stddev: float | None
    tpot_p50: float | None
    tpot_p99: float | None
    tpot_mean: float | None
    e2e_p50: float | None
    e2e_p99: float | None
    e2e_mean: float | None
    output_tps_mean: float | None
    output_tps_per_user: float | None
    total_tps_mean: float | None
    requests_per_sec: float | None
    goodput_rps: float | None
    total_requests: int | None
    successful_requests: int | None
    failed_requests: int | None
    total_input_tokens: int | None
    total_output_tokens: int | None
    peak_gpu_mem_mb: int | None
    avg_gpu_util_pct: float | None
    peak_gpu_util_pct: float | None
    peak_ram_mb: int | None
    avg_cpu_pct: float | None
    avg_power_watts: float | None
    energy_joules: float | None
    container_start_ms: int | None
    model_load_ms: int | None
    first_ready_ms: int | None
    tokens_per_joule: float | None
    tokens_per_gb_vram: float | None
    computed_at: datetime

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
