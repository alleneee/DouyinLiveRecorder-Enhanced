"""Remove session time fields from video_segments

Revision ID: remove_segment_session_2025
Revises: add_session_fields_2025
Create Date: 2025-01-20

移除video_segments表中的冗余字段:
- session_started_at: 会话开始时间已在live_rooms表中维护
- session_ended_at: 会话结束时间已在live_rooms表中维护

理由:
- 会话(session)的时间信息应该只在live_rooms表中维护
- 第一个分片开始时设置room.current_session_started_at
- 最后一个分片结束时设置room.current_session_ended_at
- video_segments表只需要保存分片本身的时间信息
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'remove_segment_session_2025'
down_revision: Union[str, None] = 'add_session_fields_2025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    移除video_segments表的冗余session时间字段
    """
    with op.batch_alter_table('video_segments', schema=None) as batch_op:
        batch_op.drop_index('ix_video_segments_session_started_at')
        batch_op.drop_column('session_started_at')
        batch_op.drop_column('session_ended_at')


def downgrade() -> None:
    """
    恢复video_segments表的session时间字段
    """
    with op.batch_alter_table('video_segments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_ended_at', mysql.DATETIME(), nullable=True, comment='会话结束时间'))
        batch_op.add_column(sa.Column('session_started_at', mysql.DATETIME(), nullable=False, comment='会话开始时间'))
        batch_op.create_index('ix_video_segments_session_started_at', ['session_started_at'], unique=False)
