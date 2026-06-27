"""add limits table

Revision ID: d6e4f5a7b8c9
Revises: c5d3e4f6a7b8
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd6e4f5a7b8c9'
down_revision = 'c5d3e4f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    limits = op.create_table('limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False),
        sa.Column('unit', sa.String(), server_default='cost_usd', nullable=False),
        sa.Column('amount', sa.Numeric(10, 4), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope', 'unit', name='uq_limits_scope_unit'),
    )
    # Conservative seed defaults (USD/day) — admin-editable via PUT /admin/limits
    op.bulk_insert(limits, [
        {'scope': 'user_guest', 'unit': 'cost_usd', 'amount': 0.25},
        {'scope': 'user_registered', 'unit': 'cost_usd', 'amount': 2.00},
        {'scope': 'global_guest', 'unit': 'cost_usd', 'amount': 10.00},
    ])


def downgrade():
    op.drop_table('limits')
