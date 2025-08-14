"""add price table

Revision ID: 1876c1c4bc96
Revises: 831fc2cf16ee
Create Date: 2025-08-11 17:57:04.438535

"""
from alembic import op
import sqlalchemy as sa
from csv import DictReader
from datetime import datetime, UTC, timedelta
import os
import decimal

# revision identifiers, used by Alembic.
revision = '1876c1c4bc96'
down_revision = '831fc2cf16ee'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create model_pricing table
    op.create_table(
        'model_pricing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('input_token_price', sa.DECIMAL(precision=12, scale=8), nullable=False),
        sa.Column('output_token_price', sa.DECIMAL(precision=12, scale=8), nullable=False),
        sa.Column('cached_token_price', sa.DECIMAL(precision=12, scale=8), nullable=False, server_default=sa.text('0')),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('price_source', sa.String(length=50), nullable=False, server_default='manual'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for model_pricing
    op.create_index('ix_model_pricing_active', 'model_pricing', 
                   ['provider_name', 'model_name', 'effective_date', 'end_date'])
    op.create_index('ix_model_pricing_temporal', 'model_pricing', 
                   ['effective_date', 'end_date'])
    op.create_index('ix_model_pricing_unique_period', 'model_pricing', 
                   ['provider_name', 'model_name', 'effective_date'], unique=True)
    op.create_index(op.f('ix_model_pricing_provider_name'), 'model_pricing', ['provider_name'])
    op.create_index(op.f('ix_model_pricing_model_name'), 'model_pricing', ['model_name'])
    op.create_index(op.f('ix_model_pricing_id'), 'model_pricing', ['id'])

    # Create fallback_pricing table
    op.create_table(
        'fallback_pricing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_name', sa.String(), nullable=True),
        sa.Column('fallback_type', sa.String(length=20), nullable=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('input_token_price', sa.DECIMAL(precision=12, scale=8), nullable=False),
        sa.Column('output_token_price', sa.DECIMAL(precision=12, scale=8), nullable=False),
        sa.Column('cached_token_price', sa.DECIMAL(precision=12, scale=8), nullable=False, server_default=sa.text('0')),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for fallback_pricing
    op.create_index('ix_fallback_pricing_active', 'fallback_pricing', 
                   ['provider_name', 'fallback_type', 'effective_date', 'end_date'])
    op.create_index('ix_fallback_pricing_type', 'fallback_pricing', 
                   ['fallback_type', 'effective_date'])
    op.create_index(op.f('ix_fallback_pricing_provider_name'), 'fallback_pricing', ['provider_name'])
    op.create_index(op.f('ix_fallback_pricing_fallback_type'), 'fallback_pricing', ['fallback_type'])
    op.create_index(op.f('ix_fallback_pricing_id'), 'fallback_pricing', ['id'])

    # Insert model pricing data
    effective_date = datetime.now(UTC) - timedelta(days=30)
    csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "data", "model_pricing_init.csv")
    with open(csv_path, "r") as f:
        reader = DictReader(f)
        rows_to_insert = []
        for row in reader:
            rows_to_insert.append({
                "provider_name": row["provider_name"],
                "model_name": row["model_name"],
                "effective_date": effective_date,
                "input_token_price": decimal.Decimal(str(row["input_token_price"])).normalize(),
                "output_token_price": decimal.Decimal(str(row["output_token_price"])).normalize(),    
                "price_source": "manual"
            })
    if rows_to_insert:
        connection = op.get_bind()
        connection.execute(
            sa.text("""
                INSERT INTO model_pricing (provider_name, model_name, effective_date, input_token_price, output_token_price, price_source)
                VALUES (:provider_name, :model_name, :effective_date, :input_token_price, :output_token_price, 'manual')
            """),
            rows_to_insert,
        )
    
    # Insert some initial fallback pricing data
    # For all the providers in the model_pricing table, insert a fallback pricing record with the provider_default fallback_type, set the prcie to be the average of the input_token_price and output_token_price
    # For global fallback, set the provider_name to NULL, and the fallback_type to global_default, and the price to be the average of the input_token_price and output_token_price of all the providers in the model_pricing table
    # The effective_date should be the same as the effective_date of the model_pricing table
    
    # Get all unique providers from model_pricing table
    providers_result = connection.execute(
        sa.text("SELECT DISTINCT provider_name FROM model_pricing")
    ).fetchall()
    
    fallback_rows = []
    
    # Insert provider-specific fallback pricing
    for provider_row in providers_result:
        provider_name = provider_row[0]
        
        # Calculate average prices for this provider
        avg_prices_result = connection.execute(
            sa.text("""
                SELECT 
                    AVG(input_token_price) as avg_input_price,
                    AVG(output_token_price) as avg_output_price
                FROM model_pricing 
                WHERE provider_name = :provider_name
            """),
            {"provider_name": provider_name}
        ).fetchone()
        
        avg_input_price = avg_prices_result[0]
        avg_output_price = avg_prices_result[1]
        
        fallback_rows.append({
            "provider_name": provider_name,
            "fallback_type": "provider_default",
            "effective_date": effective_date,
            "input_token_price": avg_input_price,
            "output_token_price": avg_output_price,
            "description": f"Default pricing for {provider_name} provider"
        })
    
    # Calculate global average prices
    global_avg_result = connection.execute(
        sa.text("""
            SELECT 
                AVG(input_token_price) as avg_input_price,
                AVG(output_token_price) as avg_output_price
            FROM model_pricing
        """)
    ).fetchone()
    
    global_avg_input_price = global_avg_result[0]
    global_avg_output_price = global_avg_result[1]
    
    # Insert global fallback pricing
    fallback_rows.append({
        "provider_name": None,
        "fallback_type": "global_default",
        "effective_date": effective_date,
        "input_token_price": global_avg_input_price,
        "output_token_price": global_avg_output_price,
        "description": "Global default pricing for all providers"
    })
    
    # Insert fallback pricing data
    if fallback_rows:
        connection.execute(
            sa.text("""
                INSERT INTO fallback_pricing (provider_name, fallback_type, effective_date, input_token_price, output_token_price, description)
                VALUES (:provider_name, :fallback_type, :effective_date, :input_token_price, :output_token_price, :description)
            """),
            fallback_rows,
        )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('fallback_pricing')
    op.drop_table('model_pricing')
