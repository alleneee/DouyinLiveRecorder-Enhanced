"""Add recording configuration fields to rooms table

Revision ID: 20250115_0001
Revises: 3ad2685fb6df
Create Date: 2025-01-15 13:15:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250115_0001'
down_revision = '3ad2685fb6df'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加录制配置字段到 rooms 表
    op.add_column('rooms', sa.Column('enable_segment_recording', sa.Boolean(), nullable=False, server_default='1', comment='启用分段录制'))
    op.add_column('rooms', sa.Column('segment_duration', sa.Integer(), nullable=False, server_default='1200', comment='分段时长（秒）'))
    op.add_column('rooms', sa.Column('video_save_type', sa.String(20), nullable=False, server_default='TS', comment='视频保存格式'))
    op.add_column('rooms', sa.Column('oss_enabled', sa.Boolean(), nullable=True, comment='是否启用OSS上传'))
    op.add_column('rooms', sa.Column('run_post_process', sa.Boolean(), nullable=False, server_default='1', comment='是否执行后处理'))
    
    # 添加录制任务表
    op.create_table(
        'recording_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('room_url', sa.String(500), nullable=False, comment='直播间 URL'),
        sa.Column('nickname', sa.String(100), nullable=False, comment='主播昵称'),
        sa.Column('quality', sa.String(20), nullable=False, server_default='OD', comment='画质代码'),
        sa.Column('enable_segment_recording', sa.Boolean(), nullable=False, server_default='1', comment='启用分段录制'),
        sa.Column('segment_duration', sa.Integer(), nullable=False, server_default='1200', comment='分段时长（秒）'),
        sa.Column('video_save_type', sa.String(20), nullable=False, server_default='TS', comment='视频保存格式'),
        sa.Column('oss_enabled', sa.Boolean(), nullable=True, comment='是否启用OSS上传'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', comment='任务状态: pending/running/stopped/error'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='开始时间'),
        sa.Column('stopped_at', sa.DateTime(), nullable=True, comment='停止时间'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.Index('idx_room_url', 'room_url'),
        sa.Index('idx_status', 'status'),
        sa.Index('idx_created_at', 'created_at'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        comment='录制任务表'
    )


def downgrade() -> None:
    op.drop_table('recording_tasks')
    op.drop_column('rooms', 'run_post_process')
    op.drop_column('rooms', 'oss_enabled')
    op.drop_column('rooms', 'video_save_type')
    op.drop_column('rooms', 'segment_duration')
    op.drop_column('rooms', 'enable_segment_recording')
