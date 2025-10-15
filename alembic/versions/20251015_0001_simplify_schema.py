"""简化数据库schema，删除冗余表

Revision ID: 20251015_0001
Revises: 20250115_0001
Create Date: 2025-10-15 17:17:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '20251015_0001'
down_revision = '20250115_0001'
branch_labels = None
depends_on = None


def upgrade():
    """升级：简化表结构"""
    
    # 1. 给 rooms 表添加录制状态相关字段
    op.add_column('rooms', sa.Column('recording_status', sa.String(20), 
                                      server_default='idle', nullable=False,
                                      comment='录制状态: idle/recording/error'))
    op.add_column('rooms', sa.Column('recording_started_at', sa.DateTime(), 
                                      nullable=True, comment='当前录制开始时间'))
    op.add_column('rooms', sa.Column('current_recording_file', sa.String(500), 
                                      nullable=True, comment='当前录制文件路径'))
    
    # 2. 添加统计字段
    op.add_column('rooms', sa.Column('total_segments', sa.Integer(), 
                                      server_default='0', nullable=False,
                                      comment='总分段数'))
    op.add_column('rooms', sa.Column('total_size_bytes', sa.BigInteger(), 
                                      server_default='0', nullable=False,
                                      comment='总文件大小（字节）'))
    op.add_column('rooms', sa.Column('last_recording_at', sa.DateTime(), 
                                      nullable=True, comment='最后录制时间'))
    
    # 3. 添加错误信息字段
    op.add_column('rooms', sa.Column('last_error', sa.Text(), 
                                      nullable=True, comment='最后错误信息'))
    op.add_column('rooms', sa.Column('error_count', sa.Integer(), 
                                      server_default='0', nullable=False,
                                      comment='错误次数'))
    
    # 4. 创建索引
    op.create_index('idx_recording_status', 'rooms', ['recording_status'])
    
    # 5. 删除冗余表（保留数据迁移的可能性）
    # 注意：如果需要保留历史数据，应该先迁移到新结构
    op.drop_table('recordings')
    op.drop_table('recording_tasks')


def downgrade():
    """降级：恢复旧表结构"""
    
    # 1. 重建 recordings 表
    op.create_table('recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE')
    )
    
    # 2. 重建 recording_tasks 表
    op.create_table('recording_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_url', sa.String(500), nullable=False),
        sa.Column('nickname', sa.String(100), nullable=False),
        sa.Column('quality', sa.String(20), server_default='OD'),
        sa.Column('enable_segment_recording', sa.Boolean(), server_default='1'),
        sa.Column('segment_duration', sa.Integer(), server_default='1200'),
        sa.Column('video_save_type', sa.String(20), server_default='TS'),
        sa.Column('oss_enabled', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('stopped_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 3. 删除索引
    op.drop_index('idx_recording_status', table_name='rooms')
    
    # 4. 删除新增字段
    op.drop_column('rooms', 'error_count')
    op.drop_column('rooms', 'last_error')
    op.drop_column('rooms', 'last_recording_at')
    op.drop_column('rooms', 'total_size_bytes')
    op.drop_column('rooms', 'total_segments')
    op.drop_column('rooms', 'current_recording_file')
    op.drop_column('rooms', 'recording_started_at')
    op.drop_column('rooms', 'recording_status')
