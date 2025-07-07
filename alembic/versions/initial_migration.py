"""initial migration

Revision ID: initial_migration
Revises:
Create Date: 2023-05-01 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "initial_migration"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("forge_api_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(
        op.f("ix_users_forge_api_key"), "users", ["forge_api_key"], unique=True
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Create provider_keys table
    op.create_table(
        "provider_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=True),
        sa.Column("encrypted_api_key", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column("model_mapping", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_keys_id"), "provider_keys", ["id"], unique=False)
    op.create_index(
        op.f("ix_provider_keys_provider_name"),
        "provider_keys",
        ["provider_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provider_keys_provider_name"), table_name="provider_keys")
    op.drop_index(op.f("ix_provider_keys_id"), table_name="provider_keys")
    op.drop_table("provider_keys")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_forge_api_key"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
