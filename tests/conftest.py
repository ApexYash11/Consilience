"""
Pytest configuration and shared fixtures for Consilience tests.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import Base, UserDB
from models.payment import SubscriptionTier, SubscriptionStatus
from models.user import UserResponse


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
    Base.metadata.drop_all(test_db_engine)
    Base.metadata.create_all(test_db_engine)
    
    yield session
    session.close()


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "full_name": "Test User",
        "neon_user_id": "neon_user_123",
        "subscription_tier": SubscriptionTier.FREE,
        "subscription_status": SubscriptionStatus.ACTIVE,
        "is_active": True,
    }


@pytest.fixture
def test_user_db(db_session, test_user_data):
    """Create a test user in the database."""
    user = UserDB(**test_user_data, hashed_password="hashed_password_123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_response(test_user_db):
    """Create a UserResponse from test user."""
    return UserResponse(
        id=test_user_db.id,
        email=test_user_db.email,
        full_name=test_user_db.full_name,
        subscription_tier=str(test_user_db.subscription_tier),
        created_at=test_user_db.created_at,
    )


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
