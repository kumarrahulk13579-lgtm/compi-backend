"""add global_total limit scope

Revision ID: e7f5a6b8c9d0
Revises: d6e4f5a7b8c9
Create Date: 2026-06-28 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


revision = 'e7f5a6b8c9d0'
down_revision = 'd6e4f5a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    limits = table('limits',
        column('scope', sa.String),
        column('unit', sa.String),
        column('amount', sa.Numeric),
    )
    # Overall daily spend ceiling across ALL users (guests + registered) — a generous
    # circuit breaker; admin-editable via PUT /admin/limits.
    op.bulk_insert(limits, [
        {'scope': 'global_total', 'unit': 'cost_usd', 'amount': 50.00},
    ])


def downgrade():
    op.execute("DELETE FROM limits WHERE scope = 'global_total' AND unit = 'cost_usd'")
