"""删除room表的oss_enabled字段

Revision ID: 20251015_0002
Revises: 20251015_0001
Create Date: 2025-10-15 17:23:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251015_0002'
down_revision = '20251015_0001'
branch_labels = None
depends_on = None


def upgrade():
    """删除oss_enabled字段"""
    op.drop_column('rooms', 'oss_enabled')


def downgrade():
    """恢复oss_enabled字段"""
    op.add_column('rooms', sa.Column('oss_enabled', sa.Integer(), nullable=True))
