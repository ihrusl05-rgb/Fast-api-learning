"""add event logs table

Revision ID: 20260530_02
Revises: 20260526_01
Create Date: 2026-05-30 22:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260530_02"
down_revision: Union[str, None] = "20260526_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("partition", sa.Integer(), nullable=False),
        sa.Column("offset", sa.BigInteger(), nullable=False),
        sa.Column("message_key", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("table_name", sa.String(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "topic",
            "partition",
            "offset",
            name="uq_event_logs_topic_partition_offset",
        ),
    )


def downgrade() -> None:
    op.drop_table("event_logs")
