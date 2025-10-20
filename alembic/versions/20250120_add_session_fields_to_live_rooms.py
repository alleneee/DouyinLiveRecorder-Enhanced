"""add_session_fields_to_live_rooms

添加会话追踪字段到 live_rooms 表:
- current_session_ended_at: 当前会话结束时间
- total_segment: 会话完成后的总分片数

Revision ID: add_session_fields_2025
Revises: remove_redundant_2025
Create Date: 2025-01-20 12:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'add_session_fields_2025'
down_revision: Union[str, None] = 'remove_redundant_2025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    添加会话追踪字段

    新增字段:
    - current_session_ended_at: 记录当前会话的结束时间,配合current_session_started_at使用
    - total_segment: 会话完成或关播后记录总分片数,作为快照数据避免频繁查询
    """
    with op.batch_alter_table('live_rooms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('current_session_ended_at', sa.DateTime(), nullable=True, comment='当前会话结束时间'))
        batch_op.add_column(sa.Column('total_segment', sa.Integer(), nullable=True, server_default='0', comment='会话完成后的总分片数'))


def downgrade() -> None:
    """
    回滚:删除会话追踪字段
    """
    with op.batch_alter_table('live_rooms', schema=None) as batch_op:
        batch_op.drop_column('total_segment')
        batch_op.drop_column('current_session_ended_at')
