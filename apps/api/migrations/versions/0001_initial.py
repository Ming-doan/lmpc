"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table("admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table("sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_table("secrets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "label"),
    )
    op.create_table("workers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("secret_hash", sa.String(), nullable=False),
        sa.Column("gpu_model", sa.String(), nullable=True),
        sa.Column("gpu_count", sa.Integer(), nullable=True),
        sa.Column("vram_mb", sa.Integer(), nullable=True),
        sa.Column("cpu", sa.String(), nullable=True),
        sa.Column("ram_mb", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="online"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table("benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_source", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("hardware", postgresql.JSONB(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("inference_container_id", sa.String(), nullable=True),
        sa.Column("inference_endpoint", sa.String(), nullable=True),
        sa.Column("avg_latency_ms", sa.Numeric(), nullable=True),
        sa.Column("avg_throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("avg_ttft_ms", sa.Numeric(), nullable=True),
        sa.Column("avg_tps", sa.Numeric(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_leaderboard", "benchmark_runs", ["is_public", "completed_at"])
    op.create_index("ix_runs_status", "benchmark_runs", ["status"])
    op.create_index("ix_runs_provider_model", "benchmark_runs", ["provider", "model_id"])

    op.create_table("benchmark_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("step_status", sa.String(), nullable=False),
        sa.Column("progress_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_steps_run_created", "benchmark_steps", ["run_id", "created_at"])

    op.create_table("benchmark_metric_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("t_offset_ms", sa.Integer(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Numeric(), nullable=True),
        sa.Column("throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms", sa.Numeric(), nullable=True),
        sa.Column("tps", sa.Numeric(), nullable=True),
        sa.Column("cpu_pct", sa.Numeric(), nullable=True),
        sa.Column("gpu_pct", sa.Numeric(), nullable=True),
        sa.Column("ram_mb", sa.Numeric(), nullable=True),
        sa.Column("vram_mb", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table("benchmark_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("requests_total", sa.Integer(), nullable=False),
        sa.Column("requests_success", sa.Integer(), nullable=False),
        sa.Column("requests_failed", sa.Integer(), nullable=False),
        sa.Column("ttft_ms_p50", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms_p95", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms_p99", sa.Numeric(), nullable=True),
        sa.Column("tpot_ms_p50", sa.Numeric(), nullable=True),
        sa.Column("tpot_ms_p95", sa.Numeric(), nullable=True),
        sa.Column("tpot_ms_p99", sa.Numeric(), nullable=True),
        sa.Column("throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("per_req_tps_p50", sa.Numeric(), nullable=True),
        sa.Column("input_tokens_avg", sa.Numeric(), nullable=True),
        sa.Column("output_tokens_avg", sa.Numeric(), nullable=True),
        sa.Column("duration_s", sa.Numeric(), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "concurrency"),
    )
    op.create_table("models_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("params_billions", sa.Numeric(), nullable=True),
        sa.Column("quantization", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "model_id"),
    )

def downgrade() -> None:
    for tbl in ["models_cache", "benchmark_results", "benchmark_metric_snapshots",
                "benchmark_steps", "benchmark_runs", "workers", "secrets", "sessions", "admins"]:
        op.drop_table(tbl)
