"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hostname", sa.String(255)),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("approved", sa.Boolean, server_default="false", nullable=False),
        sa.Column("api_token_hash", sa.String(255), nullable=False),
        sa.Column("specs", postgresql.JSONB, server_default="{}", nullable=False),
        sa.Column("capabilities", postgresql.JSONB),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_workers_status", "workers", ["status"])
    op.create_index("ix_workers_last_heartbeat_at", "workers", ["last_heartbeat_at"])

    op.create_table(
        "platforms",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100)),
        sa.Column("adapter_class", sa.String(100)),
        sa.Column("default_image", sa.String(255)),
        sa.Column("default_port", sa.Integer),
        sa.Column("default_args", postgresql.JSONB),
        sa.Column("description", sa.Text),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "models",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hf_id", sa.String(255)),
        sa.Column("size_b", sa.Numeric(6, 2)),
        sa.Column("quantization", sa.String(30)),
        sa.Column("context_length", sa.Integer),
        sa.Column("metadata", postgresql.JSONB),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "prompt_sets",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("prompts", postgresql.JSONB, nullable=False),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "run_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("platform_id", sa.Integer, nullable=False),
        sa.Column("model_id", sa.Integer, nullable=False),
        sa.Column("prompt_set_id", sa.Integer, nullable=False),
        sa.Column("platform_args", postgresql.JSONB),
        sa.Column("benchmark_args", postgresql.JSONB, nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"]),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"]),
        sa.ForeignKeyConstraint(["prompt_set_id"], ["prompt_sets.id"]),
    )

    op.create_table(
        "benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True)),
        sa.Column("iteration", sa.Integer, server_default="1"),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("attempt", sa.Integer, server_default="0"),
        sa.Column("max_attempts", sa.Integer, server_default="3"),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("leased_until", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("image_digest", sa.String(128)),
        sa.Column("platform_version", sa.String(50)),
        sa.Column("resolved_args", postgresql.JSONB),
        sa.Column("worker_specs_snapshot", postgresql.JSONB),
        sa.Column("container_id", sa.String(64)),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["config_id"], ["run_configs.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
    )
    op.create_index("idx_queue_pickup", "benchmark_runs", ["status", "priority", "queued_at"])
    op.create_index("ix_benchmark_runs_worker_status", "benchmark_runs", ["worker_id", "status"])
    op.create_index("ix_benchmark_runs_config_id", "benchmark_runs", ["config_id"])

    op.create_table(
        "benchmark_results",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ttft_p50", sa.Numeric(10, 2)), sa.Column("ttft_p90", sa.Numeric(10, 2)),
        sa.Column("ttft_p95", sa.Numeric(10, 2)), sa.Column("ttft_p99", sa.Numeric(10, 2)),
        sa.Column("ttft_mean", sa.Numeric(10, 2)), sa.Column("ttft_stddev", sa.Numeric(10, 2)),
        sa.Column("tpot_p50", sa.Numeric(10, 2)), sa.Column("tpot_p99", sa.Numeric(10, 2)),
        sa.Column("tpot_mean", sa.Numeric(10, 2)),
        sa.Column("e2e_p50", sa.Numeric(10, 2)), sa.Column("e2e_p99", sa.Numeric(10, 2)),
        sa.Column("e2e_mean", sa.Numeric(10, 2)),
        sa.Column("output_tps_mean", sa.Numeric(10, 2)), sa.Column("output_tps_per_user", sa.Numeric(10, 2)),
        sa.Column("total_tps_mean", sa.Numeric(10, 2)), sa.Column("requests_per_sec", sa.Numeric(10, 2)),
        sa.Column("goodput_rps", sa.Numeric(10, 2)),
        sa.Column("total_requests", sa.Integer), sa.Column("successful_requests", sa.Integer),
        sa.Column("failed_requests", sa.Integer), sa.Column("total_input_tokens", sa.BigInteger),
        sa.Column("total_output_tokens", sa.BigInteger),
        sa.Column("peak_gpu_mem_mb", sa.Integer), sa.Column("avg_gpu_util_pct", sa.Numeric(5, 2)),
        sa.Column("peak_gpu_util_pct", sa.Numeric(5, 2)), sa.Column("peak_ram_mb", sa.Integer),
        sa.Column("avg_cpu_pct", sa.Numeric(5, 2)), sa.Column("avg_power_watts", sa.Numeric(7, 2)),
        sa.Column("energy_joules", sa.Numeric(12, 2)),
        sa.Column("container_start_ms", sa.Integer), sa.Column("model_load_ms", sa.Integer),
        sa.Column("first_ready_ms", sa.Integer),
        sa.Column("tokens_per_joule", sa.Numeric(10, 4)), sa.Column("tokens_per_gb_vram", sa.Numeric(10, 4)),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("run_id"),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
    )

    op.create_table(
        "request_traces",
        sa.Column("id", sa.BigInteger, autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_idx", sa.Integer),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ttft_ms", sa.Numeric(10, 2)), sa.Column("tpot_ms", sa.Numeric(10, 2)),
        sa.Column("e2e_ms", sa.Numeric(10, 2)), sa.Column("queue_wait_ms", sa.Numeric(10, 2)),
        sa.Column("input_tokens", sa.Integer), sa.Column("output_tokens", sa.Integer),
        sa.Column("success", sa.Boolean), sa.Column("http_status", sa.Integer),
        sa.Column("error", sa.Text),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
    )
    op.create_index("ix_request_traces_run_started", "request_traces", ["run_id", "started_at"])
    op.create_index("ix_request_traces_started_at", "request_traces", ["started_at"])

    op.create_table(
        "metric_samples",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cpu_pct", sa.Numeric(5, 2)), sa.Column("ram_used_mb", sa.Integer),
        sa.Column("ram_pct", sa.Numeric(5, 2)),
        sa.Column("gpu_index", sa.SmallInteger, server_default="0"),
        sa.Column("gpu_util_pct", sa.SmallInteger), sa.Column("gpu_mem_used_mb", sa.Integer),
        sa.Column("gpu_mem_total_mb", sa.Integer), sa.Column("gpu_temp_c", sa.SmallInteger),
        sa.Column("gpu_power_watts", sa.Numeric(7, 2)), sa.Column("gpu_sm_clock_mhz", sa.Integer),
        sa.Column("disk_read_mbps", sa.Numeric(8, 2)), sa.Column("disk_write_mbps", sa.Numeric(8, 2)),
        sa.Column("net_rx_mbps", sa.Numeric(8, 2)), sa.Column("net_tx_mbps", sa.Numeric(8, 2)),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
    )
    op.create_index("ix_metric_samples_run_time", "metric_samples", ["run_id", "time"])
    op.create_index("ix_metric_samples_worker_time", "metric_samples", ["worker_id", "time"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, autoincrement=True, nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("actor", sa.String(255)), sa.Column("action", sa.String(100)),
        sa.Column("target_type", sa.String(50)), sa.Column("target_id", sa.String(64)),
        sa.Column("payload", postgresql.JSONB),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])
    op.create_index("ix_audit_logs_time", "audit_logs", ["time"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("metric_samples")
    op.drop_table("request_traces")
    op.drop_table("benchmark_results")
    op.drop_table("benchmark_runs")
    op.drop_table("run_configs")
    op.drop_table("prompt_sets")
    op.drop_table("models")
    op.drop_table("platforms")
    op.drop_table("workers")
