"""
Pytest configuration and shared fixtures for Consilience tests.
Provides database sessions, auth fixtures, and test data builders.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4, UUID
import asyncio
import jwt
from typing import Optional

# IMPORTANT: Set DEBUG=true BEFORE importing app/settings
# This enables test-mode JWT validation (skips JWKS validation in tests)
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYTEST_CURRENT_TEST", "true")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient
from fastapi import HTTPException, status
from unittest.mock import patch, AsyncMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import Base
from api.main import app
from models.user import CurrentUser
from models.research import TaskStatus, Source


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


@pytest.fixture
def client_with_db(async_db_session):
    """Create a FastAPI TestClient with mocked database session.
    
    Overrides get_async_session dependency to use in-memory test database.
    Use this fixture for tests that need database connectivity without
    connecting to real Neon database.
    
    Returns:
        TestClient with dependencies overridden
    """
    async def override_get_async_session():
        yield async_db_session
    
    # Override the actual get_async_session from database.connection
    from database.connection import get_async_session
    app.dependency_overrides[get_async_session] = override_get_async_session
    client = TestClient(app)
    
    yield client
    
    # Clean up dependency overrides
    app.dependency_overrides.clear()


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
# JWT Authentication Fixtures (for E2E Testing)
# ============================================================================

@pytest.fixture
def valid_jwt_token(user_id: Optional[str] = None) -> str:
    """Generate a valid JWT token for testing.
    
    Creates a real JWT token with proper segments for E2E tests.
    Uses a test secret key for signature without JWKS validation.
    
    Args:
        user_id: User ID to include in token (default: test uuid)
        
    Returns:
        Encoded JWT token string (without 'Bearer ' prefix)
    """
    if user_id is None:
        user_id = str(uuid4())
    
    payload = {
        "sub": user_id,
        "email": "testuser@example.com",
        "roles": ["free"],
        "iss": "https://neonauth.example.com",
        "aud": "neondb",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }
    
    # Sign JWT with test secret (32 bytes minimum for HS256)
    test_secret = "test-secret-key-for-e2e-testing-consilience"
    token = jwt.encode(payload, test_secret, algorithm="HS256")
    return token


@pytest.fixture
def auth_headers(valid_jwt_token: str) -> dict:
    """Create authorization headers with valid JWT token.
    
    Returns:
        Dict with Authorization header containing Bearer token
    """
    return {"Authorization": f"Bearer {valid_jwt_token}"}


@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return str(uuid4())


@pytest.fixture
def user_id_with_zero_quota():
    """Generate a test user ID for quota enforcement tests."""
    return str(uuid4())


@pytest.fixture
def mock_verify_token(mocker):
    """Mock the JWT token verification to bypass JWKS validation.
    
    This allows E2E tests to work without accessing JWKS endpoints.
    Returns a mocker instance ready to use.
    """
    async def mock_verify(token: str) -> dict:
        """Mock token verification that extracts payload from JWT without validation."""
        try:
            # Decode without verification (testing only)
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
    
    return mocker.patch(
        "core.security.NeonSecurityManager.verify_token",
        side_effect=mock_verify
    )


@pytest.fixture
def override_auth_for_testing(monkeypatch):
    """Override security manager verify_token for E2E tests.
    
    All verify_token calls will decode without JWKS validation.
    Use this fixture in test classes that need auth mocking.
    Patched into: core.security.NeonSecurityManager.verify_token
    """
    async def mock_verify(self, token: str) -> dict:
        """Decode JWT without JWKS validation for testing."""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
    
    from core.security import NeonSecurityManager
    monkeypatch.setattr(NeonSecurityManager, "verify_token", mock_verify)


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
async def mock_orchestrator(mocker):
    """Mock orchestrator to return instant results."""
    
    async def mock_run_research(state):
        # Simulate successful completion
        state.status = TaskStatus.COMPLETED
        state.final_paper = "# Research Paper\n\nGenerated content."
        state.sources = [
            Source(id="source1", url="https://example.com/1", title="Source 1", credibility=0.9),
        ]
        state.cost = 1.50
        state.tokens_used = 3000
        state.end_time = datetime.utcnow()
        return state
    
    mocker.patch(
        "orchestrator.standard_orchestrator.run_research",
        side_effect=mock_run_research,
    )


@pytest.fixture
def auth_service(db_session):
    """Create a NeonAuthService with a test database session."""
    from services.neon_auth_service import NeonAuthService
    return NeonAuthService(db=db_session)
