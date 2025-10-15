"""Add video_segments table for 20min recordings

Revision ID: 3ad2685fb6df
Revises: 20240709_0001
Create Date: 2025-01-15 11:37:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3ad2685fb6df'
down_revision = '20240709_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 video_segments 表
    op.create_table(
        'video_segments',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('room_url', sa.String(500), nullable=False, comment='直播间 URL'),
        sa.Column('anchor_name', sa.String(100), nullable=False, comment='主播名称'),
        sa.Column('segment_index', sa.Integer(), nullable=False, comment='分段序号（从1开始）'),
        sa.Column('local_path', sa.String(500), nullable=False, comment='本地文件路径'),
        sa.Column('file_size', sa.BigInteger(), nullable=False, comment='文件大小（字节）'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True, comment='视频时长（秒）'),
        sa.Column('oss_key', sa.String(500), nullable=True, comment='OSS 对象键'),
        sa.Column('oss_url', sa.Text(), nullable=True, comment='OSS 访问 URL'),
        sa.Column('upload_status', sa.String(20), nullable=False, default='pending', comment='上传状态: pending/uploading/success/failed'),
        sa.Column('upload_time', sa.DateTime(), nullable=True, comment='上传完成时间'),
        sa.Column('start_time', sa.DateTime(), nullable=False, comment='录制开始时间'),
        sa.Column('end_time', sa.DateTime(), nullable=False, comment='录制结束时间'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_room_url', 'room_url'),
        sa.Index('idx_anchor_name', 'anchor_name'),
        sa.Index('idx_start_time', 'start_time'),
        sa.Index('idx_upload_status', 'upload_status'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
        comment='视频分段记录表（每20分钟一段）'
    )


def downgrade() -> None:
    op.drop_table('video_segments')
