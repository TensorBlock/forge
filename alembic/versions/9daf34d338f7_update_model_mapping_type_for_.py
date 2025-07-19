"""update model_mapping type for ProviderKey table

Revision ID: 9daf34d338f7
Revises: 08cc005a4bc8
Create Date: 2025-07-18 21:32:48.791253

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "9daf34d338f7"
down_revision = "08cc005a4bc8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change model_mapping column from String to JSON
    op.alter_column(
        "provider_keys",
        "model_mapping",
        existing_type=sa.String(),
        type_=postgresql.JSON(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="model_mapping::json",
    )


def downgrade() -> None:
    # Change model_mapping column from JSON back to String
    op.alter_column(
        "provider_keys",
        "model_mapping",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        type_=sa.String(),
        existing_nullable=True,
        postgresql_using="model_mapping::text",
    )
