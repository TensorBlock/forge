"""add billable column to usage_tracker

Revision ID: 683fc811a969
Revises: 40e4b59f754d
Create Date: 2025-09-05 10:48:09.623668

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '683fc811a969'
down_revision = '40e4b59f754d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('usage_tracker', sa.Column('billable', sa.Boolean(), nullable=False, server_default='FALSE'))


def downgrade() -> None:
    op.drop_column('usage_tracker', 'billable')
