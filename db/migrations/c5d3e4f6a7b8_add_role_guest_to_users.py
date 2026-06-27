"""add role and guest support to users

Revision ID: c5d3e4f6a7b8
Revises: b4c2d3e5f6a7
Create Date: 2026-06-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c5d3e4f6a7b8'
down_revision = 'b4c2d3e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # role + is_registered on users
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='user'))
    op.add_column('users', sa.Column('is_registered', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # every pre-existing user is a real registered account
    op.execute("UPDATE users SET is_registered = true")

    # guests have no email
    op.alter_column('users', 'email', existing_type=sa.String(), nullable=True)

    # prevent duplicate identities (this table previously had no unique constraint).
    # NULL provider_user_id (e.g. guests) stay distinct, so multiple guests are fine.
    op.create_unique_constraint(
        'uq_user_identities_provider_user', 'user_identities', ['provider', 'provider_user_id']
    )


def downgrade():
    op.drop_constraint('uq_user_identities_provider_user', 'user_identities', type_='unique')
    # leave email nullable on downgrade — forcing NOT NULL back would crash if guest rows exist
    op.drop_column('users', 'is_registered')
    op.drop_column('users', 'role')
