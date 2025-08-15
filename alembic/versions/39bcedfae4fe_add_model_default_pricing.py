"""add model default pricing

Revision ID: 39bcedfae4fe
Revises: b206e9a941e3
Create Date: 2025-08-14 18:31:20.897283

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39bcedfae4fe'
down_revision = 'b206e9a941e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('fallback_pricing', sa.Column('model_name', sa.String(), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text("""
        insert into fallback_pricing (provider_name, model_name, input_token_price, output_token_price, cached_token_price, currency, created_at, updated_at, effective_date, end_date, fallback_type, description) 
        select distinct on (model_name) 
            provider_name as provider_name, 
            model_name as model_name, 
            input_token_price, 
            output_token_price, 
            cached_token_price, 
            currency, 
            created_at, 
            updated_at, 
            effective_date, 
            end_date, 
            'model_default' as fallback_type,
            null as description
        from model_pricing
        order by model_name, 
                 case when provider_name = 'openai' then 1 
                      when provider_name = 'anthropic' then 2 
                      else 3 end
    """))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("""
        delete from fallback_pricing where fallback_type = 'model_default'
    """))
    op.drop_column('fallback_pricing', 'model_name')
