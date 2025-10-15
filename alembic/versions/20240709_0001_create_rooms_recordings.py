"""Create rooms and recordings tables.

Revision ID: 20240709_0001
Revises: 
Create Date: 2024-07-09 00:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20240709_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(length=512), nullable=False, unique=True),
        sa.Column("nickname", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("quality", sa.String(length=32), nullable=False, server_default="原画"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rooms_status", "rooms", ["status"])

    op.create_table(
        "recordings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recordings_room_id", "recordings", ["room_id"])


def downgrade() -> None:
    op.drop_index("ix_recordings_room_id", table_name="recordings")
    op.drop_table("recordings")
    op.drop_index("ix_rooms_status", table_name="rooms")
    op.drop_table("rooms")
