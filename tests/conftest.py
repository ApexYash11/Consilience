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
from unittest.mock import patch, AsyncMock, MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# Mock Heavy Dependencies BEFORE importing app
# ============================================================================
# This prevents import-time dependency issues with transformers/langchain
sys.modules['transformers'] = MagicMock()
sys.modules['langchain_openai'] = MagicMock()
sys.modules['langchain_openai.chat_models'] = MagicMock()
sys.modules['langchain_openai.chat_models.azure'] = MagicMock()

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


@pytest.fixture(scope="function", autouse=True)
def patch_async_session_local(async_test_db_engine):
    """
    Auto-patch AsyncSessionLocal for all tests.
    This ensures services like CostService use the test database.
    """
    TestAsyncSessionLocal = async_sessionmaker(
        async_test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Patch database.connection.AsyncSessionLocal to use test database
    from database import connection
    original_session_local = connection.AsyncSessionLocal
    connection.AsyncSessionLocal = TestAsyncSessionLocal
    
    yield
    
    # Restore original
    connection.AsyncSessionLocal = original_session_local


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


@pytest.fixture
def client_with_auth(async_db_session):
    """Create a FastAPI TestClient with both DB and JWT auth mocked.

    Use this for E2E API tests hitting /api/research/* or /api/payments/*
    that need a valid session and authenticated user without real Neon/JWKS.

    Returns:
        (TestClient, auth_headers dict) tuple
    """
    from database.connection import get_async_session
    from api.dependencies import get_current_user
    from core.security import NeonSecurityManager
    from models.user import CurrentUser

    # Mock DB
    async def override_get_async_session():
        yield async_db_session

    # Mock authenticated free user
    async def override_get_current_user():
        return CurrentUser(
            user_id=str(uuid4()),
            email="testuser@example.com",
            tier="free",
            roles=["free"],
        )

    # Mock paid user override (can be swapped per-test via app.dependency_overrides)
    async def override_get_paid_user():
        return CurrentUser(
            user_id=str(uuid4()),
            email="paiduser@example.com",
            tier="paid",
            roles=["paid"],
        )

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_token = _make_test_jwt(role="free")
    headers = {"Authorization": f"Bearer {test_token}"}

    client = TestClient(app)
    yield client, headers

    app.dependency_overrides.clear()


@pytest.fixture
def client_with_paid_auth(async_db_session):
    """Same as client_with_auth but with PAID tier user — for deep research endpoints."""
    from database.connection import get_async_session
    from api.dependencies import get_current_user, require_paid_tier
    from models.user import CurrentUser

    paid_id = str(uuid4())

    async def override_get_async_session():
        yield async_db_session

    async def override_get_current_user():
        return CurrentUser(
            user_id=paid_id,
            email="paiduser@example.com",
            tier="paid",
            roles=["paid"],
        )

    async def override_require_paid_tier():
        return CurrentUser(
            user_id=paid_id,
            email="paiduser@example.com",
            tier="paid",
            roles=["paid"],
        )

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_paid_tier] = override_require_paid_tier

    test_token = _make_test_jwt(role="paid")
    headers = {"Authorization": f"Bearer {test_token}"}

    client = TestClient(app)
    yield client, headers

    app.dependency_overrides.clear()


def _make_test_jwt(role: str = "free") -> str:
    """Build a signed test JWT (HS256, test secret)."""
    payload = {
        "sub": str(uuid4()),
        "email": f"{role}user@example.com",
        "roles": [role],
        "iss": "https://neonauth.example.com",
        "aud": "neondb",
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, "test-secret-key-for-e2e-testing-consilience", algorithm="HS256")


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
async def test_user_id(async_db_session) -> str:
    """Create a test user in the database and return its ID."""
    from models.payment import SubscriptionTier
    from database.schema import UserDB
    
    user_id = str(uuid4())
    
    # Create user in async session
    user = UserDB(
        id=user_id,
        email=f"testuser_{user_id[:8]}@example.com",
        subscription_tier=SubscriptionTier.FREE.value,
        monthly_standard_quota=5,
        monthly_deep_quota=3,
        standard_papers_this_month=0,
        deep_papers_this_month=0,
        total_tokens_this_month=0,
        total_cost_this_month=0.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    async_db_session.add(user)
    await async_db_session.commit()
    
    return user_id


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
