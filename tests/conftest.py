"""
Pytest configuration and shared fixtures for Consilience tests.
Provides database sessions, auth fixtures, and test data builders.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import Base
from api.main import app
from models.user import CurrentUser


# ============================================================================
# Sync Database Fixtures (for traditional tests)
# ============================================================================

@pytest.fixture(scope="session")
def test_db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """Create a new database session for each test."""
    SessionLocal = sessionmaker(bind=test_db_engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    
    # Clean up tables before each test
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    
    yield session
    session.close()


# ============================================================================
# Async Database Fixtures (for async tests)
# ============================================================================

@pytest.fixture(scope="session")
async def async_test_db_engine():
    """Create an async in-memory database for async testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session(async_test_db_engine):
    """Create a new async database session for each test."""
    AsyncSessionLocal = async_sessionmaker(
        async_test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        yield session


# ============================================================================
# FastAPI Test Client
# ============================================================================

@pytest.fixture
def client():
    """Create a FastAPI TestClient for integration tests."""
    return TestClient(app)


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def free_user() -> CurrentUser:
    """Create a free tier user object."""
    return CurrentUser(
        user_id="free_user_123",
        email="free@example.com",
        tier="free",
        roles=["free"]
    )


@pytest.fixture
def paid_user() -> CurrentUser:
    """Create a paid tier user object."""
    return CurrentUser(
        user_id="paid_user_456",
        email="paid@example.com",
        tier="paid",
        roles=["paid"]
    )


@pytest.fixture
def admin_user() -> CurrentUser:
    """Create an admin user object."""
    return CurrentUser(
        user_id="admin_user_789",
        email="admin@example.com",
        tier="paid",
        roles=["admin", "paid"]
    )


@pytest.fixture
def valid_jwt_payload() -> dict:
    """Create a valid JWT payload."""
    return {
        "sub": "user_123",
        "email": "test@example.com",
        "roles": ["free"],
        "iss": "https://neonauth.example.com",
        "aud": "neondb",
        "iat": datetime.utcnow().timestamp(),
        "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp()
    }


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Mocking Utilities
# ============================================================================

@pytest.fixture
def mock_security_manager():
    """Create a mock security manager."""
    with patch("core.security.get_security_manager") as mock:
        security_manager = mock.return_value
        security_manager.verify_token = AsyncMock()
        security_manager.extract_user_info = AsyncMock()
        security_manager.get_jwks = AsyncMock()
        yield security_manager


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    with patch("database.connection.get_async_session") as mock:
        session = AsyncMock(spec=AsyncSession)
        mock.return_value = session
        yield session


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "full_name": "Test User",
        "neon_user_id": "neon_user_123",
        "subscription_tier": "free",
        "subscription_status": "active",
        "is_active": True,
    }


@pytest.fixture
def test_user_db(db_session, test_user_data):
    """Create a test user in the database."""
    # Skip test - requires database schema to be set up
    pytest.skip("Database schema setup required")


@pytest.fixture
def test_user_response(test_user_db):
    """Create a UserResponse from test user."""
    # Placeholder for async context
    pytest.skip("Test user db required")


@pytest.fixture
def mock_token_claims():
    """Mock OAuth token claims."""
    return {
        "sub": "neon_user_456",
        "email": "newuser@example.com",
        "name": "New User",
        "role": "user",
    }


@pytest.fixture
def mock_token_claims_admin():
    """Mock OAuth token claims with admin role."""
    return {
        "sub": "neon_admin_789",
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "admin",
    }


@pytest.fixture
def auth_service(db_session):
    """Create an auth service instance for testing."""
    from services.neon_auth_service import NeonAuthService
    
    service = NeonAuthService(db=db_session)
    return service
