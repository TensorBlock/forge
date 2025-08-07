"""enable soft deletion for provider keys and api keys

Revision ID: 831fc2cf16ee
Revises: 4a685a55c5cd
Create Date: 2025-08-02 17:50:12.224293

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '831fc2cf16ee'
down_revision = '4a685a55c5cd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('provider_keys', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('forge_api_keys', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('forge_api_keys', 'key', nullable=True)


def downgrade() -> None:
    op.drop_column('provider_keys', 'deleted_at')
    op.drop_column('forge_api_keys', 'deleted_at')
    op.alter_column('forge_api_keys', 'key', nullable=False)
