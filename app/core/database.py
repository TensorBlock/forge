import os

from dotenv import load_dotenv
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Production-optimized connection pool settings
# With 10 Gunicorn workers, this allows max 60 connections total (10 workers × 3 pool_size × 2 engines)
# Plus 40 overflow connections (10 workers × 2 max_overflow × 2 engines) = 100 max connections
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "3"))  # Reduced from 5 to 3
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "2"))  # Reduced from 10 to 2
MAX_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Sync engine and session
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=MAX_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,  # Enables connection health checks
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Sync dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Async engine and session (new)
# Convert the DATABASE_URL to async format if it's using psycopg2
ASYNC_DATABASE_URL = SQLALCHEMY_DATABASE_URL
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql+psycopg2://"):
    ASYNC_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+asyncpg://")

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=MAX_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,  # Enables connection health checks
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


# Async dependency
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            # Rollback on any exception, but handle potential session state issues
            try:
                await session.rollback()
            except Exception:
                # If rollback fails (e.g., session already closed), ignore it
                # The context manager will handle session cleanup
                pass
            raise


@asynccontextmanager
async def get_db_session():
    """Async context manager for database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            # Rollback on any exception, but handle potential session state issues
            try:
                await session.rollback()
            except Exception:
                # If rollback fails (e.g., session already closed), ignore it
                # The context manager will handle session cleanup
                pass
            raise


def get_connection_info():
    """Get current connection pool information for monitoring"""
    return {
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_timeout": MAX_TIMEOUT,
        "pool_recycle": POOL_RECYCLE,
        "sync_engine": {
            "pool": engine.pool,
            "checked_out": engine.pool.checkedout(),
            "checked_in": engine.pool.checkedin(),
            "size": engine.pool.size(),
        },
        "async_engine": {
            "pool": async_engine.pool,
            "checked_out": async_engine.pool.checkedout(),
            "checked_in": async_engine.pool.checkedin(), 
            "size": async_engine.pool.size(),
        }
    }