"""OAuth service for Google and GitHub authentication."""
import httpx
import jwt
from datetime import datetime, timedelta
from typing import Optional
import logging

from sqlalchemy.orm import Session

from ..config.settings import Settings
from ..database.schema import UserDB, Base
from ..models.payment import SubscriptionTier, SubscriptionStatus
from .auth_service import AuthService

logger = logging.getLogger(__name__)


def _get_secret_value(value) -> str:
    """Safely extract secret value from SecretStr or return str.
    
    Args:
        value: Either a string or a SecretStr object
        
    Returns:
        The string value
    """
    if hasattr(value, 'get_secret_value'):
        return value.get_secret_value()
    return str(value)


class OAuthService:
    """Handle OAuth authentication for Google and GitHub."""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.auth_service = AuthService(db, settings)

    async def get_google_token(self, code: str) -> Optional[dict]:
        """Exchange Google auth code for access token."""
        if not self.settings.GOOGLE_CLIENT_ID or not self.settings.GOOGLE_CLIENT_SECRET:
            logger.error("Google OAuth credentials not configured")
            return None

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": self.settings.GOOGLE_CLIENT_ID,
                        "client_secret": _get_secret_value(self.settings.GOOGLE_CLIENT_SECRET),
                        "redirect_uri": self.settings.GOOGLE_REDIRECT_URI,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to exchange Google code: {e}")
                return None

    async def get_google_user_info(self, access_token: str) -> Optional[dict]:
        """Get user info from Google using access token."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to get Google user info: {e}")
                return None

    async def get_github_token(self, code: str) -> Optional[dict]:
        """Exchange GitHub auth code for access token."""
        if not self.settings.GITHUB_CLIENT_ID or not self.settings.GITHUB_CLIENT_SECRET:
            logger.error("GitHub OAuth credentials not configured")
            return None

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        "code": code,
                        "client_id": self.settings.GITHUB_CLIENT_ID,
                        "client_secret": _get_secret_value(self.settings.GITHUB_CLIENT_SECRET),
                        "redirect_uri": self.settings.GITHUB_REDIRECT_URI,
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to exchange GitHub code: {e}")
                return None

    async def get_github_user_info(self, access_token: str) -> Optional[dict]:
        """Get user info from GitHub using access token."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to get GitHub user info: {e}")
                return None

    def get_or_create_oauth_user(
        self,
        email: str,
        full_name: str,
        provider: str,  # 'google' or 'github'
        provider_id: str,
    ) -> Optional[UserDB]:
        """Get existing OAuth user or create new one."""
        try:
            # Check if user exists by email
            existing_user = self.db.query(UserDB).filter(UserDB.email == email).first()

            if existing_user:
                logger.info(f"OAuth user {existing_user.id} already exists via {provider}")
                return existing_user

            # Create new OAuth user
            from uuid import uuid4

            new_user = UserDB(
                id=uuid4(),
                email=email,
                full_name=full_name,
                hashed_password="!oauth:" + provider,  # Sentinel: OAuth-created user
                is_verified=True,  # OAuth providers verify emails
                is_active=True,
                subscription_tier=SubscriptionTier.FREE,
                subscription_status=SubscriptionStatus.ACTIVE,
                neon_user_id=None,
                created_at=datetime.utcnow(),
            )

            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)

            logger.info(f"Created new OAuth user {new_user.id} via {provider}")
            return new_user

        except Exception as e:
            logger.error(f"Failed to get/create OAuth user via {provider}: {e}")
            self.db.rollback()
            return None

    def generate_oauth_jwt_token(self, user: UserDB) -> str:
        """Generate JWT token for OAuth user."""
        try:
            # Handle SecretStr if JWT_SECRET is wrapped
            secret_value = _get_secret_value(self.settings.JWT_SECRET)
            
            payload = {
                "sub": str(user.id),
                "email": user.email,
                "exp": datetime.utcnow() + timedelta(hours=self.settings.JWT_EXPIRATION_HOURS),
            }
            token = jwt.encode(
                payload,
                secret_value,
                algorithm=self.settings.JWT_ALGORITHM,
            )
            return token
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {e}")
            return ""
