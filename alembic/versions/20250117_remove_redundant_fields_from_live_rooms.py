"""remove_redundant_fields_from_live_rooms

移除 live_rooms 表中的冗余字段
这些字段可以通过查询 video_segments 表获取,无需冗余存储

Revision ID: remove_redundant_2025
Revises: 4a23d6964ef9
Create Date: 2025-01-17 20:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'remove_redundant_2025'
down_revision: Union[str, None] = '4a23d6964ef9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    删除冗余字段

    删除的字段:
    - total_session_count: 可通过 COUNT(DISTINCT session_id) 计算
    - current_session_title: 不再需要,标题存在 video_segments
    - current_stream_url: 运行时信息,不需要持久化
    - current_ffmpeg_pid: 运行时信息,不需要持久化
    - last_session_*: 可通过查询最新 session 获取
    - total_segment_count: 可通过 COUNT(*) 计算
    - total_duration: 可通过 SUM(duration) 计算
    - total_file_size: 可通过文件大小统计计算
    - last_check_time: 不需要持久化
    - last_live_time: 可通过最新 session_started_at 获取
    - last_error_*: 错误信息应该单独记录,不在主表
    - error_count: 不需要持久化
    """
    # 删除所有冗余字段
    with op.batch_alter_table('live_rooms', schema=None) as batch_op:
        batch_op.drop_column('total_session_count')
        batch_op.drop_column('current_session_title')
        batch_op.drop_column('current_stream_url')
        batch_op.drop_column('current_ffmpeg_pid')
        batch_op.drop_column('last_session_id')
        batch_op.drop_column('last_session_title')
        batch_op.drop_column('last_session_started_at')
        batch_op.drop_column('last_session_ended_at')
        batch_op.drop_column('last_session_duration')
        batch_op.drop_column('last_session_segment_count')
        batch_op.drop_column('total_segment_count')
        batch_op.drop_column('total_duration')
        batch_op.drop_column('total_file_size')
        batch_op.drop_column('last_check_time')
        batch_op.drop_column('last_live_time')
        batch_op.drop_column('last_error_time')
        batch_op.drop_column('last_error_message')
        batch_op.drop_column('error_count')


def downgrade() -> None:
    """
    回滚:重新添加这些字段
    注意:数据无法恢复,只恢复表结构
    """
    with op.batch_alter_table('live_rooms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_session_count', sa.Integer(), nullable=True, comment='总录制次数'))
        batch_op.add_column(sa.Column('current_session_title', sa.String(length=255), nullable=True, comment='当前会话标题'))
        batch_op.add_column(sa.Column('current_stream_url', sa.Text(), nullable=True, comment='当前流地址'))
        batch_op.add_column(sa.Column('current_ffmpeg_pid', sa.Integer(), nullable=True, comment='当前FFmpeg进程PID'))
        batch_op.add_column(sa.Column('last_session_id', sa.String(length=36), nullable=True, comment='上次录制会话ID'))
        batch_op.add_column(sa.Column('last_session_title', sa.String(length=255), nullable=True, comment='上次会话标题'))
        batch_op.add_column(sa.Column('last_session_started_at', sa.DateTime(), nullable=True, comment='上次会话开始时间'))
        batch_op.add_column(sa.Column('last_session_ended_at', sa.DateTime(), nullable=True, comment='上次会话结束时间'))
        batch_op.add_column(sa.Column('last_session_duration', sa.Integer(), nullable=True, comment='上次会话时长(秒)'))
        batch_op.add_column(sa.Column('last_session_segment_count', sa.Integer(), nullable=True, comment='上次会话分片数'))
        batch_op.add_column(sa.Column('total_segment_count', sa.Integer(), nullable=True, comment='总分片数'))
        batch_op.add_column(sa.Column('total_duration', sa.Integer(), nullable=True, comment='总录制时长(秒)'))
        batch_op.add_column(sa.Column('total_file_size', sa.Integer(), nullable=True, comment='总文件大小(字节)'))
        batch_op.add_column(sa.Column('last_check_time', sa.DateTime(), nullable=True, comment='最后检查时间'))
        batch_op.add_column(sa.Column('last_live_time', sa.DateTime(), nullable=True, comment='最后开播时间'))
        batch_op.add_column(sa.Column('last_error_time', sa.DateTime(), nullable=True, comment='最后错误时间'))
        batch_op.add_column(sa.Column('last_error_message', sa.Text(), nullable=True, comment='最后错误信息'))
        batch_op.add_column(sa.Column('error_count', sa.Integer(), nullable=True, comment='错误次数'))
