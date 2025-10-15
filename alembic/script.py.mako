"""Mako template used by Alembic for new migration scripts."""

<%text>
"""Revision script template."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

</%text>
