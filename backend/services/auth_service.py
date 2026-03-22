"""Authentication service logic."""

from typing import Optional

from ..models.user import UserCreate, UserLogin, UserResponse, TokenResponse
from ..models.payment import SubscriptionTier


class AuthService:
    def register_user(self, user_data: UserCreate) -> UserResponse:
        # Stub logic for registration
        return UserResponse(
            id="12345678-1234-5678-1234-567812345678",
            email=user_data.email,
            full_name=user_data.full_name,
            subscription_tier=SubscriptionTier.FREE,
            subscription_status="active",
            created_at="2023-01-01T00:00:00",
        )

    def authenticate_user(self, credentials: UserLogin) -> Optional[TokenResponse]:
        # TODO: Replace with real user lookup against the database and proper
        # bcrypt password verification (see core/security.py).
        # This stub always returns None (authentication not yet implemented).
        return None
