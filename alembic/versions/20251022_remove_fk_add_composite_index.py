"""remove foreign key constraint and add composite index

Revision ID: remove_fk_20251022
Revises: remove_segment_session_2025
Create Date: 2025-10-22 10:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'remove_fk_20251022'
down_revision: Union[str, None] = 'remove_segment_session_2025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库schema - 移除外键约束并添加联合索引"""
    # 删除外键约束
    op.drop_constraint('video_segments_ibfk_1', 'video_segments', type_='foreignkey')

    # 添加联合索引 (platform, platform_room_id, session_id)
    op.create_index(
        'idx_platform_room_session',
        'video_segments',
        ['platform', 'platform_room_id', 'session_id'],
        unique=False
    )


def downgrade() -> None:
    """回滚数据库schema - 恢复外键约束并删除联合索引"""
    # 删除联合索引
    op.drop_index('idx_platform_room_session', table_name='video_segments')

    # 恢复外键约束
    op.create_foreign_key(
        'video_segments_ibfk_1',
        'video_segments',
        'live_rooms',
        ['room_id'],
        ['id'],
        ondelete='CASCADE'
    )
