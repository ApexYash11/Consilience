"""
Database connection and session management for Consilience API.
Async connections for FastAPI.
"""

import os
from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
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
_sync_connect_args = {}
if "postgresql" in DATABASE_URL:
    # Use standard PostgreSQL connection
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
    
    # Extract sslmode from URL query string and pass as connect_arg for psycopg2
    parsed = urlparse(DATABASE_URL)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    if 'sslmode' in query_params:
        sslmode = query_params['sslmode'][0]
        if sslmode == 'require':
            _sync_connect_args['sslmode'] = 'require'
        # Remove from URL since psycopg2 gets it from connect_args
        query_params.pop('sslmode', None)
        
        # Rebuild URL without sslmode
        new_query = urlencode(
            {k: v[0] if len(v) == 1 else v for k, v in query_params.items()},
            doseq=True
        )
        if new_query:
            SYNC_DATABASE_URL = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
        else:
            SYNC_DATABASE_URL = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                '',
                parsed.fragment
            ))
else:
    SYNC_DATABASE_URL = DATABASE_URL

_engine = create_engine(
    SYNC_DATABASE_URL,
    future=True,
    poolclass=NullPool,  # Disable pooling - create fresh connection every time
    echo=False,
    connect_args=_sync_connect_args
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _clean_postgres_url(db_url: str) -> str:
    """
    Clean PostgreSQL URL by removing asyncpg-specific parameters.
    
    Removes asyncpg-incompatible query params using proper URL parsing.
    These parameters are specific to asyncpg and should not be passed to the async driver.
    
    Args:
        db_url: PostgreSQL URL (may have asyncpg-specific params)
        
    Returns:
        Cleaned URL with asyncpg-specific params removed
    """
    # Parse the URL
    parsed = urlparse(db_url)
    
    # Parse query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Remove asyncpg-incompatible parameters
    params_to_remove = ['async_fallback', 'sslrootcert', 'sslmode']
    for param in params_to_remove:
        query_params.pop(param, None)
    
    # Rebuild query string (parse_qs returns lists for values, so flatten them)
    new_query = urlencode(
        {k: v[0] if len(v) == 1 else v for k, v in query_params.items()},
        doseq=True
    )
    
    # Reassemble URL
    new_parsed = (
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    )
    return urlunparse(new_parsed)


# Create async engine for FastAPI
async_connect_args = {}
if "postgresql" in DATABASE_URL:
    # Replace postgresql:// with postgresql+asyncpg://
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    # Map sslmode from URL query to asyncpg-compatible connect arg.
    parsed = urlparse(DATABASE_URL)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    sslmode = (query_params.get("sslmode") or [None])[0]
    if sslmode == "require":
        async_connect_args = {"ssl": "require"}
    
    # Clean up asyncpg-specific parameters while keeping psycopg2-compatible ones
    ASYNC_DATABASE_URL = _clean_postgres_url(ASYNC_DATABASE_URL)
    
    # Enforce SSL in production even if URL omitted sslmode.
    if REQUIRE_SSL and "ssl" not in async_connect_args:
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


def get_db_session():
    """
    Synchronous session generator for FastAPI dependency injection.
    
    Used for services that require sync database operations (like AuthService).
    FastAPI will automatically call this and manage the session lifecycle.
    
    Example:
        @app.post("/register")
        def register(user_data: UserCreate, db: Session = Depends(get_db_session)):
            ...
    """
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
    from .schema import Base
    
    Base.metadata.create_all(bind=_engine)


async def close_db() -> None:
    """Close async database connections."""
    await async_engine.dispose()
