#!/usr/bin/env python
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.sql import text

load_dotenv()

# Get connection string from environment variable
conn_string = os.environ.get("DATABASE_URL")
if not conn_string:
    print("Please set the DATABASE_URL environment variable")
    sys.exit(1)

engine = create_engine(conn_string)

with engine.connect() as connection:
    try:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO alembic_version VALUES ('6a92c2663fa5')"))
        connection.commit()
        print("Successfully reset alembic version to 6a92c2663fa5")
    except Exception as e:
        print(f"Error resetting alembic version: {e}")
        print("Error: No version found in alembic_version table")
        sys.exit(1)
