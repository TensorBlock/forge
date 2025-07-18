import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Sync engine and session
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
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
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    echo=False,  # Set to True for debugging SQL queries
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


# Async dependency
# TODO: Add async dependency to the API routes
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
