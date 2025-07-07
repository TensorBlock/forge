"""add_clerk_user_id_to_users

Revision ID: b5d4363a9f62
Revises: 0ce4eeae965f
Create Date: 2025-04-19 10:43:37.264983

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b5d4363a9f62"
down_revision = "0ce4eeae965f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add clerk_user_id column to users table
    op.add_column("users", sa.Column("clerk_user_id", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_users_clerk_user_id"), "users", ["clerk_user_id"], unique=True
    )

    # SQLite doesn't support ALTER COLUMN directly, use batch operations instead
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "hashed_password", existing_type=sa.String(), nullable=True
        )


def downgrade() -> None:
    # Remove clerk_user_id column
    op.drop_index(op.f("ix_users_clerk_user_id"), table_name="users")
    op.drop_column("users", "clerk_user_id")

    # Make hashed_password required again
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "hashed_password", existing_type=sa.String(), nullable=False
        )
