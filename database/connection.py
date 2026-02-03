"""
Database connection and session management for Consilience API.
Supports both sync (for Alembic) and async (for FastAPI) operations.
"""

import os
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from dotenv import load_dotenv

load_dotenv()

# Get database URL and convert to async driver if needed
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for local development
    DATABASE_URL = "sqlite:///./consilience.db"

# Create sync engine for Alembic migrations
if "postgresql" in DATABASE_URL:
    # For Alembic, use standard PostgreSQL connection
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
else:
    SYNC_DATABASE_URL = DATABASE_URL

_engine = create_engine(
    SYNC_DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    echo=False
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

    # Provide ssl handling via asyncpg connect args if needed
    async_connect_args = {"ssl": "prefer"}
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
    """Synchronous session generator for Alembic."""
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
    """Initialize async database and create tables."""
    from database.schema import Base
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db():
    """Initialize sync database (used by Alembic)."""
    from database.schema import Base
    
    Base.metadata.create_all(bind=_engine)


async def close_db():
    """Close async database connections."""
    await async_engine.dispose()
