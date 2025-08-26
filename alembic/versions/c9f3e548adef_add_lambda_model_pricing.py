"""add lambda model pricing

Revision ID: c9f3e548adef
Revises: 39bcedfae4fe
Create Date: 2025-08-25 19:53:57.606298

"""
from csv import DictReader
from decimal import Decimal
import os
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timedelta, UTC


# revision identifiers, used by Alembic.
revision = 'c9f3e548adef'
down_revision = '39bcedfae4fe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # insert the lambda data
    effective_date = datetime.now(UTC) - timedelta(days=1)
    csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "data", "lambda_model_pricing_init.csv")
    with open(csv_path, "r") as f:
        reader = DictReader(f)
        rows_to_insert = []
        for row in reader:
            rows_to_insert.append({
                "provider_name": row["provider_name"],
                "model_name": row["model_name"],
                "effective_date": effective_date,
                "input_token_price": Decimal(str(row["input_token_price"])).normalize(),
                "output_token_price": Decimal(str(row["output_token_price"])).normalize(),    
                "price_source": "manual"
            })
    
    if rows_to_insert:
        connection = op.get_bind()
        connection.execute(
            sa.text("""
                INSERT INTO model_pricing (provider_name, model_name, effective_date, input_token_price, output_token_price, cached_token_price, price_source)
                VALUES (:provider_name, :model_name, :effective_date, :input_token_price, :output_token_price, :input_token_price, 'manual')
            """),
            rows_to_insert,
        )
        connection.execute(
            sa.text("""
                INSERT INTO fallback_pricing (provider_name, model_name, effective_date, input_token_price, output_token_price, cached_token_price, fallback_type)
                VALUES (:provider_name, :model_name, :effective_date, :input_token_price, :output_token_price, :input_token_price, 'model_default')
            """),
            rows_to_insert,
        )
    
    # Fix the cached_token_price for all the other models
    csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "data", "model_pricing_init.csv")
    with open(csv_path, "r") as f:
        reader = DictReader(f)
        rows_to_update = []
        for row in reader:
            rows_to_update.append({
                "provider_name": row["provider_name"],
                "model_name": row["model_name"],
                "input_token_price": Decimal(str(row["input_token_price"])).normalize(),
                "output_token_price": Decimal(str(row["output_token_price"])).normalize(),    
                "cached_token_price": Decimal(str(row["cached_token_price"])).normalize(),
            })
    
    if rows_to_update:
        connection = op.get_bind()
        connection.execute(
            sa.text("""
                update model_pricing set cached_token_price = :cached_token_price
                where provider_name = :provider_name and model_name = :model_name
            """),
            rows_to_update,
        )
        connection.execute(
            sa.text("""
                update fallback_pricing set cached_token_price = :cached_token_price
                where provider_name = :provider_name and model_name = :model_name
            """),
            rows_to_update,
        )
    
    # backfill the cached_token_price for all the other models
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            with updated_model_pricing as (
                update model_pricing set cached_token_price = input_token_price
                where cached_token_price = 0
            )
            update fallback_pricing set cached_token_price = input_token_price
            where cached_token_price = 0
        """),
        rows_to_insert,
    )

    # remove the default value for cached_token_price
    op.alter_column('model_pricing', 'cached_token_price', server_default=None)
    op.alter_column('fallback_pricing', 'cached_token_price', server_default=None)


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            DELETE FROM model_pricing WHERE provider_name = 'lambda'
        """),
    )
    connection.execute(
        sa.text("""
            DELETE FROM fallback_pricing WHERE provider_name = 'lambda'
        """),
    )
