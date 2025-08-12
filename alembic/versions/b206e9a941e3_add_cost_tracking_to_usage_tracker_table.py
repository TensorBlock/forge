"""add cost tracking to usage_tracker table

Revision ID: b206e9a941e3
Revises: 1876c1c4bc96
Create Date: 2025-08-11 18:19:08.581296

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b206e9a941e3'
down_revision = '1876c1c4bc96'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('usage_tracker', sa.Column('cost', sa.DECIMAL(precision=12, scale=8), nullable=True))
    op.add_column('usage_tracker', sa.Column('currency', sa.String(length=3), nullable=True))
    op.add_column('usage_tracker', sa.Column('pricing_source', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('usage_tracker', 'cost')
    op.drop_column('usage_tracker', 'currency')
    op.drop_column('usage_tracker', 'pricing_source')
