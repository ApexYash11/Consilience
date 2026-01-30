"""
Unit tests for NeonAuthService.
"""

import pytest
from uuid import UUID

from models.user import UserResponse
from models.payment import SubscriptionTier


class TestNeonAuthService:
    """Test suite for NeonAuthService."""

    def test_map_role_to_tier_admin(self, auth_service):
        """Test role to tier mapping for admin."""
        tier = auth_service.map_role_to_tier("admin")
        assert tier == SubscriptionTier.PRO

    def test_map_role_to_tier_user(self, auth_service):
        """Test role to tier mapping for regular user."""
        tier = auth_service.map_role_to_tier("user")
        assert tier == SubscriptionTier.FREE

    def test_map_role_to_tier_default(self, auth_service):
        """Test role to tier mapping for unknown role."""
        tier = auth_service.map_role_to_tier("unknown")
        assert tier == SubscriptionTier.FREE

    def test_get_or_create_user_new(self, auth_service, mock_token_claims):
        """Test creating a new user from token claims."""
        user = auth_service.get_or_create_user(mock_token_claims)
        
        assert isinstance(user, UserResponse)
        assert user.email == mock_token_claims["email"]
        assert user.full_name == mock_token_claims["name"]
        assert user.subscription_tier == SubscriptionTier.FREE.value
        assert isinstance(user.id, UUID)

    def test_get_or_create_user_existing(self, auth_service, test_user_db, mock_token_claims):
        """Test getting an existing user."""
        # Create user with matching neon_user_id
        test_user_db.neon_user_id = mock_token_claims["sub"]
        auth_service.db.commit()
        
        user = auth_service.get_or_create_user(mock_token_claims)
        
        assert user.email == test_user_db.email
        assert isinstance(user.id, UUID)

    def test_get_or_create_user_upgrade_tier(self, auth_service, test_user_db):
        """Test upgrading user tier via token claims."""
        test_user_db.neon_user_id = "neon_admin_123"
        auth_service.db.commit()
        
        token_claims = {
            "sub": "neon_admin_123",
            "email": test_user_db.email,
            "name": test_user_db.full_name,
            "role": "admin",
        }
        
        user = auth_service.get_or_create_user(token_claims)
        assert user.subscription_tier == SubscriptionTier.PRO.value

    def test_get_user_by_email_found(self, auth_service, test_user_db):
        """Test retrieving user by email."""
        user = auth_service.get_user_by_email(test_user_db.email)
        
        assert user is not None
        assert user.email == test_user_db.email
        assert isinstance(user.id, UUID)

    def test_get_user_by_email_not_found(self, auth_service):
        """Test retrieving non-existent user by email."""
        user = auth_service.get_user_by_email("nonexistent@example.com")
        assert user is None

    def test_get_user_by_id(self, auth_service, test_user_db):
        """Test retrieving user by neon_user_id."""
        user = auth_service.get_user_by_id(test_user_db.neon_user_id)
        
        assert user is not None
        assert user.email == test_user_db.email

    def test_get_user_by_id_not_found(self, auth_service):
        """Test retrieving non-existent user by neon_user_id."""
        user = auth_service.get_user_by_id("nonexistent_neon_id")
        assert user is None

    def test_enforce_tier_access_free_user_free_resource(self, auth_service, test_user_response):
        """Test free user accessing free resource."""
        test_user_response.subscription_tier = SubscriptionTier.FREE.value
        # Free resources don't require tier check (required_tier defaults to "paid")
        # This should raise for pro resources
        with pytest.raises(Exception):
            auth_service.enforce_tier_access(test_user_response, required_tier="pro")

    def test_enforce_tier_access_paid_user_free_resource(self, auth_service, test_user_response):
        """Test paid user can access resources."""
        test_user_response.subscription_tier = SubscriptionTier.PRO.value
        result = auth_service.enforce_tier_access(test_user_response, required_tier="pro")
        assert result is True

    def test_enforce_tier_access_free_user_free_resource_explicit(self, auth_service, test_user_response):
        """Test free user accessing free resource explicitly."""
        test_user_response.subscription_tier = SubscriptionTier.FREE.value
        result = auth_service.enforce_tier_access(test_user_response, required_tier="free")
        assert result is True


class TestTokenVerification:
    """Test OAuth token verification."""

    def test_verify_token_valid_structure(self, auth_service):
        """Test verifying token with valid structure."""
        # Note: This would require mocking JWT verification
        # For now, test that method exists and is callable
        assert hasattr(auth_service, "verify_token")
        assert callable(auth_service.verify_token)
