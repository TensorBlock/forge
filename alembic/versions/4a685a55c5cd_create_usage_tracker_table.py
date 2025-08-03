"""create usage tracker table

Revision ID: 4a685a55c5cd
Revises: 9daf34d338f7
Create Date: 2025-08-02 12:29:07.955645

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = '4a685a55c5cd'
down_revision = '9daf34d338f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_tracker",
        sa.Column("id", UUID(as_uuid=True), nullable=False, primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_key_id", sa.Integer(), nullable=False),
        sa.Column("forge_key_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("endpoint", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),

        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_key_id"], ["provider_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["forge_key_id"], ["forge_api_keys.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("usage_tracker")
