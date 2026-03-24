"""
Database connection and session management for Consilience API.
Async connections for FastAPI.
"""

import os
import re
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from dotenv import load_dotenv

load_dotenv()

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
IS_TEST = os.getenv("PYTEST_CURRENT_TEST") is not None
REQUIRE_SSL = ENVIRONMENT == "production"

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
    # Replace postgresql:// with postgresql+asyncpg://
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    # Strip sslmode=require and channel_binding=require from query string using regex
    # This preserves the password and all other parts of the URL correctly
    ASYNC_DATABASE_URL = re.sub(r'[?&]sslmode=[^&]*', '', ASYNC_DATABASE_URL)
    ASYNC_DATABASE_URL = re.sub(r'[?&]channel_binding=[^&]*', '', ASYNC_DATABASE_URL)
    # Clean up multiple ? or leading &
    ASYNC_DATABASE_URL = re.sub(r'\?&', '?', ASYNC_DATABASE_URL)
    ASYNC_DATABASE_URL = re.sub(r'\?$', '', ASYNC_DATABASE_URL)
    
    # Neon ALWAYS requires SSL, regardless of environment
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
    
    # Parse PostgreSQL URL using SQLAlchemy's make_url()
    # This robustly handles database names with hyphens, query parameters, and all edge cases
    try:
        url_obj = make_url(url_str)
    except (ArgumentError, ValueError) as ve:
        # make_url() parsing failed - URL is malformed
        # SQLAlchemy raises ArgumentError; keep ValueError for backward compatibility
        # SECURITY: Only include URL in debug/test mode to prevent credential leakage
        if DEBUG or IS_TEST:
            raise ValueError(f"Invalid DATABASE_URL format: {url_str}") from ve
        else:
            raise ValueError("Invalid DATABASE_URL format") from ve

    user = url_obj.username
    password = url_obj.password
    host = url_obj.host
    port = url_obj.port or 5432
    database = url_obj.database
    
    if user and password and host and database:
        # Test raw asyncpg connection (verify DB is reachable)
        # Only use SSL in production, not in test environments
        ssl_mode = 'require' if REQUIRE_SSL else None
        
        try:
            conn = await asyncpg.connect(
                host=host,
                port=port,
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
            # Log but continue in test mode (include URL only in debug logs)
            import logging
            logging.warning(f"Database connection warning (test mode): {str(e)}")
    else:
        # SECURITY: Don't expose DATABASE_URL in error messages
        if DEBUG or IS_TEST:
            raise ValueError(f"Invalid DATABASE_URL format (missing credentials): {url_str}")
        else:
            raise ValueError("Invalid DATABASE_URL format (missing required credentials)")


def init_db():
    """Initialize sync database (legacy, use async version instead)."""
    from database.schema import Base
    
    Base.metadata.create_all(bind=_engine)


async def close_db() -> None:
    """Close async database connections."""
    await async_engine.dispose()
