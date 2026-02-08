"""
Database connection and session management for Consilience API.
Async connections for FastAPI.
"""

import os
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from dotenv import load_dotenv

load_dotenv()

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
IS_TEST = os.getenv("PYTEST_CURRENT_TEST") is not None or DEBUG
REQUIRE_SSL = ENVIRONMENT == "production" and not IS_TEST

# Get database URL and convert to async driver if needed
DATABASE_URL: str = os.getenv("DATABASE_URL") or "sqlite:///./consilience.db"

# Create sync engine (kept for backward compatibility if needed)
if "postgresql" in DATABASE_URL:
    # Use standard PostgreSQL connection
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
    
    # Parse and remove query parameters that psycopg2 doesn't support
    url_obj = make_url(SYNC_DATABASE_URL)
    query_params = dict(url_obj.query)
    cleaned_query = {
        key: value
        for key, value in query_params.items()
        if key.lower() not in ("sslmode", "channel_binding")
    }
    url_obj = url_obj.set(query=cleaned_query)
    SYNC_DATABASE_URL = str(url_obj)
else:
    SYNC_DATABASE_URL = DATABASE_URL

_sync_connect_args = {}
if "postgresql" in DATABASE_URL and REQUIRE_SSL:
    _sync_connect_args = {"sslmode": "require"}

_engine = create_engine(
    SYNC_DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    echo=False,
    connect_args=_sync_connect_args
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


# Create async engine for FastAPI
async_connect_args = {}
if "postgresql" in DATABASE_URL:
    # Ensure asyncpg scheme
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    # Parse URL and remove only the sslmode (and channel_binding) query parameters, preserving others
    url_obj = make_url(ASYNC_DATABASE_URL)
    query_params = dict(url_obj.query)
    cleaned_query = {
        key: value
        for key, value in query_params.items()
        if key.lower() not in ("sslmode", "channel_binding")
    }
    url_obj = url_obj.set(query=cleaned_query)
    ASYNC_DATABASE_URL = str(url_obj)

    # Only require SSL in production
    if REQUIRE_SSL:
        async_connect_args = {"ssl": "require"}
elif "sqlite" in DATABASE_URL and "aiosqlite" not in DATABASE_URL:
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
    async_connect_args = {}
else:
    ASYNC_DATABASE_URL = DATABASE_URL
    async_connect_args = {}

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    echo=False,
    pool_size=20,
    max_overflow=0,
    pool_recycle=3600,
    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


def get_session():
    """Synchronous session generator (deprecated, kept for backward compatibility)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Asynchronous session generator for FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_async_db():
    """Initialize async database and verify connection.
    
    No Alembic - just test the connection.
    Tables are already created in Neon. For new databases, run:
      from database.schema import Base
      from database.connection import _engine
      Base.metadata.create_all(_engine)
    """
    import re
    
    # Skip connection test for SQLite (in-memory test databases)
    if DATABASE_URL and "sqlite" in DATABASE_URL:
        return
    
    try:
        import asyncpg
    except ImportError:
        # asyncpg not installed, skip connection test
        return
    
    # Extract connection details from DATABASE_URL
    url_str = DATABASE_URL
    if not url_str:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    match = re.match(r'postgresql[+\w]*://([^:]+):([^@]+)@([^/]+)/(\w+)', url_str)
    if match:
        user, password, host, database = match.groups()
        
        # Test raw asyncpg connection (verify DB is reachable)
        # Only use SSL in production, not in test environments
        ssl_mode = 'require' if REQUIRE_SSL else None
        
        try:
            conn = await asyncpg.connect(
                host=host,
                port=5432,
                user=user,
                password=password,
                database=database,
                ssl=ssl_mode,
                timeout=10
            )
            await conn.close()
        except Exception as e:
            # In test/debug mode, don't fail hard on connection errors
            if not (DEBUG or IS_TEST):
                raise
            # Log but continue in test mode
            import logging
            logging.warning(f"Database connection warning (test mode): {str(e)}")
    else:
        raise ValueError(f"Invalid DATABASE_URL format: {url_str}")


def init_db():
    """Initialize sync database (legacy, use async version instead)."""
    from database.schema import Base
    
    Base.metadata.create_all(bind=_engine)


async def close_db() -> None:
    """Close async database connections."""
    await async_engine.dispose()
