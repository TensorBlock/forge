"""create_forge_api_keys_table

Revision ID: 4a82fb8af123
Revises: b5d4363a9f62
Create Date: 2023-05-15 12:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "4a82fb8af123"
down_revision = "b5d4363a9f62"  # Update this to point to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Create forge_api_keys table
    op.create_table(
        "forge_api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        op.f("ix_forge_api_keys_id"), "forge_api_keys", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_forge_api_keys_key"), "forge_api_keys", ["key"], unique=True
    )

    # Migrate existing keys
    # This will create a new entry in forge_api_keys for each user's existing forge_api_key
    op.execute(
        """
        INSERT INTO forge_api_keys (key, name, user_id, is_active, created_at)
        SELECT forge_api_key, 'Legacy API Key', id, is_active, created_at
        FROM users
        WHERE forge_api_key IS NOT NULL
        """
    )


def downgrade():
    # Drop the table
    op.drop_index(op.f("ix_forge_api_keys_key"), table_name="forge_api_keys")
    op.drop_index(op.f("ix_forge_api_keys_id"), table_name="forge_api_keys")
    op.drop_table("forge_api_keys")
