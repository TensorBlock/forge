#!/usr/bin/env python3
"""
Script to directly check the database for API keys.
"""

import os

import psycopg2
from dotenv import load_dotenv


def check_database_connection():
    """Check if database is accessible."""
    try:
        # Load environment variables
        load_dotenv()

        # Get database URL from environment
        db_url = os.getenv(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/forge"
        )

        # Try to connect to PostgreSQL
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        print("Please ensure:")
        print("1. PostgreSQL is running")
        print("2. Database 'forge' exists")
        print("3. User has proper permissions")
        print("4. Connection details in .env are correct")
        return None


def main():
    """Check the database for API keys."""
    conn = check_database_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        # Get table names
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """
        )
        tables = cursor.fetchall()
        print(f"Tables in database: {[table[0] for table in tables]}")

        # Check if users table exists
        if ("users",) in tables:
            # Count users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"Number of users in database: {user_count}")

            # Get user details
            cursor.execute("SELECT id, username, forge_api_key FROM users")
            users = cursor.fetchall()

            print("\nUsers in database:")
            for user_id, username, api_key in users:
                print(f"User {user_id} ({username}): API Key = {api_key}")

                # Check against the expected key
                expected_key = "forge-1ea5812207aa309110b4122f38d7be34"
                if api_key == expected_key:
                    print("  ✓ Matches expected key")
                else:
                    print("  ✗ Does not match expected key")
        else:
            print("'users' table not found in database")

        # Check if provider_keys table exists
        if ("provider_keys",) in tables:
            cursor.execute("SELECT COUNT(*) FROM provider_keys")
            key_count = cursor.fetchone()[0]
            print(f"\nNumber of provider keys in database: {key_count}")

            # Get provider key details
            cursor.execute("SELECT id, provider_name, user_id FROM provider_keys")
            keys = cursor.fetchall()

            print("\nProvider keys in database:")
            for key_id, provider_name, user_id in keys:
                print(f"Key {key_id}: Provider = {provider_name}, User ID = {user_id}")

        cursor.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
