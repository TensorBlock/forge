"""add stripe payment table

Revision ID: 40e4b59f754d
Revises: a58395ea1b22
Create Date: 2025-09-02 20:52:29.183031

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, UTC


# revision identifiers, used by Alembic.
revision = '40e4b59f754d'
down_revision = 'a58395ea1b22'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('stripe_payment',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount', sa.Integer, nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('raw_data', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=datetime.now(UTC)),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=datetime.now(UTC), onupdate=datetime.now(UTC)),
    )


def downgrade() -> None:
    op.drop_table('stripe_payment')
