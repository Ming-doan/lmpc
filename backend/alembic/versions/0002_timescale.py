"""timescaledb extensions and hypertables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        SELECT create_hypertable(
            'metric_samples', 'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
        """
    )
    op.execute(
        """
        SELECT create_hypertable(
            'request_traces', 'started_at',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
        """
    )


def downgrade() -> None:
    # Hypertables cannot be easily reverted; drop extensions only
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
