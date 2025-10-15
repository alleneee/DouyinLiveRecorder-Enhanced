"""删除room表的current_recording_file字段

Revision ID: 20251015_0003
Revises: 20251015_0002
Create Date: 2025-10-15 17:25:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251015_0003'
down_revision = '20251015_0002'
branch_labels = None
depends_on = None


def upgrade():
    """删除current_recording_file字段"""
    op.drop_column('rooms', 'current_recording_file')


def downgrade():
    """恢复current_recording_file字段"""
    op.add_column('rooms', sa.Column('current_recording_file', sa.String(500), nullable=True))
