"""add balance system

Revision ID: a58395ea1b22
Revises: c9f3e548adef
Create Date: 2025-08-20 22:00:45.743308

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a58395ea1b22'
down_revision = 'c9f3e548adef'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'wallets',
        sa.Column('account_id', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.CHAR(length=3), nullable=False, server_default='USD'),
        sa.Column('balance', sa.DECIMAL(precision=20, scale=6), nullable=False, server_default='0'),
        sa.Column('blocked', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('version', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('account_id'),
        sa.ForeignKeyConstraint(['account_id'], ['users.id'], ondelete='CASCADE')
    )
    op.add_column('provider_keys', sa.Column('billable', sa.Boolean(), nullable=False, server_default='FALSE'))


def downgrade() -> None:
    op.drop_table('wallets')
    op.drop_column('provider_keys', 'billable')