"""add depends_on to plan_steps

Revision ID: b4c2d3e5f6a7
Revises: a3f1e2d4b5c6
Create Date: 2026-06-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b4c2d3e5f6a7'
down_revision = 'a3f1e2d4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('plan_steps', sa.Column('depends_on', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('plan_steps', 'depends_on')
