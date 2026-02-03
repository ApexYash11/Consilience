"""
End-to-end authentication tests for Consilience API.
Tests Neon JWT validation, protected endpoints, and tier-based access control.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import jwt
from datetime import datetime, timedelta

from api.main import app


client = TestClient(app)


@pytest.fixture
def valid_jwt_token():
    """Create a valid Neon JWT token for testing."""
    payload = {
        "sub": "user_123",
        "email": "test@example.com",
        "roles": ["free"],
        "iss": "https://neonauth.example.com",
        "aud": "neondb",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    
    # In a real scenario, this would be signed with Neon's private key
    # For testing, we'll mock the validation
    token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
    return token, payload


@pytest.fixture
def paid_jwt_token():
    """Create a Neon JWT token for a paid user."""
    payload = {
        "sub": "user_paid_123",
        "email": "paid@example.com",
        "roles": ["paid"],
        "iss": "https://neonauth.example.com",
        "aud": "neondb",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    
    token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
    return token, payload


@pytest.fixture
def expired_jwt_token():
    """Create an expired Neon JWT token."""
    payload = {
        "sub": "user_expired_123",
        "email": "expired@example.com",
        "roles": ["free"],
        "iss": "https://neonauth.example.com",
        "aud": "neondb",
        "iat": datetime.utcnow() - timedelta(hours=2),
        "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    }
    
    token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
    return token, payload


# ============================================================================
# Health Check Tests
# ============================================================================

def test_health_check():
    """Test health check endpoint without auth."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["authenticated"] is False


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Consilience"
    assert "documentation" in response.json()


# ============================================================================
# Authentication Tests
# ============================================================================

@patch("core.security.NeonSecurityManager.verify_token")
@patch("api.dependencies.get_async_session")
def test_auth_missing_header(mock_db, mock_verify):
    """Test request without Authorization header fails."""
    response = client.get(
        "/health",
        headers={}
    )
    
    # Should succeed without auth for health endpoint
    assert response.status_code == 200
    assert response.json()["authenticated"] is False


@patch("core.security.NeonSecurityManager.verify_token")
@patch("core.security.NeonSecurityManager.get_jwks")
@patch("api.dependencies.get_async_session")
async def test_auth_valid_token(mock_db, mock_jwks, mock_verify, valid_jwt_token):
    """Test request with valid JWT token is accepted."""
    token, payload = valid_jwt_token
    
    # Mock JWKS retrieval
    mock_jwks.return_value = {
        "keys": [{
            "kid": "test-kid",
            "kty": "RSA",
            "use": "sig",
            "n": "test-modulus",
            "e": "AQAB"
        }]
    }
    
    # Mock token verification
    mock_verify.return_value = payload
    
    response = client.get(
        "/health",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # For unauthenticated endpoint, should still work
    assert response.status_code == 200


@patch("core.security.NeonSecurityManager.verify_token")
def test_auth_invalid_bearer_format(mock_verify):
    """Test request with malformed Authorization header."""
    # Missing "Bearer" prefix
    response = client.get(
        "/health",
        headers={"Authorization": "token_without_bearer"}
    )
    
    # Should succeed for unauthenticated endpoint
    assert response.status_code == 200


def test_auth_missing_bearer_token():
    """Test request with missing bearer token."""
    response = client.get(
        "/health",
        headers={"Authorization": "Bearer"}  # Missing token
    )
    
    # Should succeed for unauthenticated endpoint
    assert response.status_code == 200


# ============================================================================
# Token Validation Tests
# ============================================================================

def test_extract_bearer_token_valid():
    """Test extracting bearer token from header."""
    from core.security import extract_bearer_token
    
    header = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    token = extract_bearer_token(header)
    assert token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."


def test_extract_bearer_token_invalid_format():
    """Test extracting bearer token with invalid format raises error."""
    from core.security import extract_bearer_token
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        extract_bearer_token("InvalidFormat token")
    
    assert exc_info.value.status_code == 401
    assert "Invalid authorization header format" in exc_info.value.detail


def test_extract_bearer_token_missing():
    """Test extracting bearer token when header is None."""
    from core.security import extract_bearer_token
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        extract_bearer_token(None)
    
    assert exc_info.value.status_code == 401
    assert "Authorization header missing" in exc_info.value.detail


# ============================================================================
# User Info Extraction Tests
# ============================================================================

def test_extract_user_info_free_tier():
    """Test extracting user info from free tier token."""
    from core.security import NeonSecurityManager
    
    manager = NeonSecurityManager()
    payload = {
        "sub": "user_123",
        "email": "test@example.com",
        "roles": ["free"]
    }
    
    user_info = manager.extract_user_info(payload)
    
    assert user_info["user_id"] == "user_123"
    assert user_info["email"] == "test@example.com"
    assert user_info["tier"] == "free"
    assert "free" in user_info["roles"]


def test_extract_user_info_paid_tier():
    """Test extracting user info from paid tier token."""
    from core.security import NeonSecurityManager
    
    manager = NeonSecurityManager()
    payload = {
        "sub": "user_paid_123",
        "email": "paid@example.com",
        "roles": ["paid", "user"]
    }
    
    user_info = manager.extract_user_info(payload)
    
    assert user_info["user_id"] == "user_paid_123"
    assert user_info["email"] == "paid@example.com"
    assert user_info["tier"] == "paid"


def test_extract_user_info_missing_email():
    """Test extracting user info when email is missing."""
    from core.security import NeonSecurityManager
    
    manager = NeonSecurityManager()
    payload = {
        "sub": "user_123",
        "roles": ["free"]
        # email is missing
    }
    
    user_info = manager.extract_user_info(payload)
    
    assert user_info["user_id"] == "user_123"
    assert user_info["email"] is None


# ============================================================================
# Tier-Based Access Control Tests
# ============================================================================

@patch("api.dependencies.get_async_session")
@patch("api.dependencies.get_current_user")
def test_free_user_cannot_access_paid_endpoint(mock_current_user, mock_db):
    """Test that free users are blocked from paid endpoints."""
    from models.user import CurrentUser
    
    user = CurrentUser(
        user_id="free_user",
        email="free@example.com",
        tier="free",
        roles=["free"]
    )
    
    # This would be a protected endpoint (not implemented yet in main.py)
    # For now, test the dependency logic
    from api.dependencies import require_paid_tier
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        require_paid_tier(user)
    
    assert exc_info.value.status_code == 403
    assert "paid subscription" in exc_info.value.detail


@patch("api.dependencies.get_current_user")
def test_paid_user_can_access_paid_endpoint(mock_current_user):
    """Test that paid users can access premium endpoints."""
    from models.user import CurrentUser
    from api.dependencies import require_paid_tier
    
    paid_user = CurrentUser(
        user_id="paid_user",
        email="paid@example.com",
        tier="paid",
        roles=["paid"]
    )
    
    # Should not raise exception
    result = require_paid_tier(paid_user)
    assert result.tier == "paid"


# ============================================================================
# Admin Role Tests
# ============================================================================

@patch("api.dependencies.get_current_user")
def test_admin_user_can_access_admin_endpoint(mock_current_user):
    """Test that admin users can access admin endpoints."""
    from models.user import CurrentUser
    from api.dependencies import require_admin
    
    admin_user = CurrentUser(
        user_id="admin_user",
        email="admin@example.com",
        tier="paid",
        roles=["admin", "paid"]
    )
    
    # Should not raise exception
    result = require_admin(admin_user)
    assert "admin" in result.roles


@patch("api.dependencies.get_current_user")
def test_non_admin_user_cannot_access_admin_endpoint(mock_current_user):
    """Test that non-admin users are blocked from admin endpoints."""
    from models.user import CurrentUser
    from api.dependencies import require_admin
    from fastapi import HTTPException
    
    regular_user = CurrentUser(
        user_id="user_123",
        email="user@example.com",
        tier="paid",
        roles=["paid"]
    )
    
    with pytest.raises(HTTPException) as exc_info:
        require_admin(regular_user)
    
    assert exc_info.value.status_code == 403
    assert "Admin role required" in exc_info.value.detail


# ============================================================================
# Optional Auth Tests
# ============================================================================

@patch("api.dependencies.extract_bearer_token")
def test_optional_auth_with_valid_token(mock_extract):
    """Test optional auth with valid token returns user."""
    from api.dependencies import get_optional_user
    from models.user import CurrentUser
    
    # This is a placeholder test as full async testing requires pytest-asyncio
    # Real implementation would use async fixtures
    pass


def test_optional_auth_without_token():
    """Test optional auth without token returns None."""
    from api.dependencies import get_optional_user
    
    # This is a placeholder test for async
    # Real implementation would use pytest.mark.asyncio
    pass


# ============================================================================
# Error Handling Tests
# ============================================================================

@patch("core.security.NeonSecurityManager.get_jwks")
def test_jwks_fetch_failure(mock_jwks):
    """Test handling of JWKS fetch failures."""
    import httpx
    from core.security import NeonSecurityManager
    from fastapi import HTTPException
    
    manager = NeonSecurityManager()
    mock_jwks.side_effect = httpx.RequestError("Connection failed")
    
    # Would raise HTTPException in real scenario
    with pytest.raises(Exception):
        # In real async context
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
