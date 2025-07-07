#!/usr/bin/env python3
"""
Test script to verify PostgreSQL migration.
"""

import os

import psycopg2
from dotenv import load_dotenv


def test_connection():
    """Test database connection."""
    print("Testing database connection...")
    try:
        load_dotenv()
        db_url = os.getenv(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/forge"
        )
        conn = psycopg2.connect(db_url)
        print("✓ Database connection successful")
        return conn
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return None


def test_schema(conn):
    """Test database schema."""
    print("\nTesting database schema...")
    cursor = conn.cursor()

    # Check tables
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
    """
    )
    tables = [table[0] for table in cursor.fetchall()]
    expected_tables = {"users", "provider_keys", "api_request_log", "alembic_version"}
    missing_tables = expected_tables - set(tables)
    extra_tables = set(tables) - expected_tables

    if missing_tables:
        print(f"✗ Missing tables: {missing_tables}")
    if extra_tables:
        print(f"✗ Unexpected tables: {extra_tables}")
    if not missing_tables and not extra_tables:
        print("✓ All expected tables present")

    # Check users table structure
    print("\nTesting users table structure...")
    cursor.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'users'
    """
    )
    columns = {row[0]: row[1] for row in cursor.fetchall()}
    expected_columns = {
        "id": "integer",
        "email": "character varying",
        "username": "character varying",
        "hashed_password": "character varying",
        "is_active": "boolean",
        "forge_api_key": "character varying",
        "clerk_user_id": "character varying",
        "created_at": "timestamp without time zone",
        "updated_at": "timestamp without time zone",
    }

    missing_columns = set(expected_columns.keys()) - set(columns.keys())
    wrong_types = {
        col
        for col, type_ in expected_columns.items()
        if col in columns and columns[col] != type_
    }

    if missing_columns:
        print(f"✗ Missing columns: {missing_columns}")
    if wrong_types:
        print(f"✗ Wrong column types: {wrong_types}")
    if not missing_columns and not wrong_types:
        print("✓ Users table structure correct")

    # Check provider_keys table structure
    print("\nTesting provider_keys table structure...")
    cursor.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'provider_keys'
    """
    )
    columns = {row[0]: row[1] for row in cursor.fetchall()}
    expected_columns = {
        "id": "integer",
        "provider_name": "character varying",
        "encrypted_api_key": "character varying",
        "user_id": "integer",
        "base_url": "character varying",
        "model_mapping": "character varying",
        "created_at": "timestamp without time zone",
        "updated_at": "timestamp without time zone",
    }

    missing_columns = set(expected_columns.keys()) - set(columns.keys())
    wrong_types = {
        col
        for col, type_ in expected_columns.items()
        if col in columns and columns[col] != type_
    }

    if missing_columns:
        print(f"✗ Missing columns: {missing_columns}")
    if wrong_types:
        print(f"✗ Wrong column types: {wrong_types}")
    if not missing_columns and not wrong_types:
        print("✓ Provider_keys table structure correct")

    # Check api_request_log table structure
    print("\nTesting api_request_log table structure...")
    cursor.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'api_request_log'
    """
    )
    columns = {row[0]: row[1] for row in cursor.fetchall()}
    expected_columns = {
        "id": "integer",
        "user_id": "integer",
        "provider_name": "character varying",
        "model": "character varying",
        "endpoint": "character varying",
        "request_timestamp": "timestamp without time zone",
        "input_tokens": "integer",
        "output_tokens": "integer",
        "total_tokens": "integer",
        "cost": "double precision",
    }

    missing_columns = set(expected_columns.keys()) - set(columns.keys())
    wrong_types = {
        col
        for col, type_ in expected_columns.items()
        if col in columns and columns[col] != type_
    }

    if missing_columns:
        print(f"✗ Missing columns: {missing_columns}")
    if wrong_types:
        print(f"✗ Wrong column types: {wrong_types}")
    if not missing_columns and not wrong_types:
        print("✓ Api_request_log table structure correct")

    cursor.close()


def main():
    """Run all tests."""
    conn = test_connection()
    if conn:
        try:
            test_schema(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
