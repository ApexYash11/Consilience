import os
import logging
import httpx
import jwt
from jwt import PyJWKClient
from datetime import datetime
from typing import Optional, Dict
from uuid import UUID
from jose import JWTError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from models.user import UserResponse
from models.payment import SubscriptionTier
from database.schema import UserDB as User

# Neon auth endpoints from environment
JWKS_URL = os.getenv("JWKS_URL", "")
AUTH_URL = os.getenv("AUTH_URL", "")

# Role to tier mapping
ROLE_TO_TIER = {
    "admin": SubscriptionTier.PRO,
    "premium": SubscriptionTier.PRO,
    "pro": SubscriptionTier.PRO,
    "free_user": SubscriptionTier.FREE,
    "user": SubscriptionTier.FREE,
}


class NeonAuthService:
    """Synchronous Neon auth helper using SQLAlchemy Session.

    This implementation intentionally uses blocking DB calls and
    synchronous HTTP for JWKS so it matches the current project
    structure and test fixtures.
    """

    def __init__(self, db: Session):
        self.db = db
        self._jwks_cache = None
        self._cache_time = None
    
    def _get_tier_value(self, tier) -> str:
        """Extract the string value from a SubscriptionTier enum."""
        if hasattr(tier, 'value'):
            return str(tier.value)
        return str(tier)

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange OAuth code for token. Neon often returns JWT directly.

        For Neon-managed flow we accept the authorization code as the
        token (the frontend may receive a JWT directly depending on
        Neon configuration).
        """
        if not code:
            raise JWTError("Authorization code is required")
        return code

    def map_role_to_tier(self, neon_role: str) -> SubscriptionTier:
        return ROLE_TO_TIER.get((neon_role or "").lower(), SubscriptionTier.FREE)

    def verify_token(self, token: str) -> Dict:
        """Verify and decode a JWT token using JWKS from Neon.

        Returns a dict of claims on success.
        """
        if not token:
            raise JWTError("Token is required")

        try:
            # Enforce signature verification using JWKS when configured.
            if not JWKS_URL:
                # Fail fast: do not allow skipping verification in production
                raise JWTError("JWKS_URL not configured; cannot verify token signature")

            try:
                # Use PyJWKClient to fetch keys and select the correct signing key for this token
                jwk_client = PyJWKClient(JWKS_URL)
                signing_key = jwk_client.get_signing_key_from_jwt(token)
                public_key = signing_key.key
            except Exception as e:
                # Surface JWKS/key retrieval failures
                logger.exception("Failed to fetch or parse JWKS from %s", JWKS_URL)
                raise JWTError(f"Failed to obtain signing key from JWKS: {e}")

            # Decode and verify signature. Adjust algorithms/audience/issuer as needed.
            try:
                payload = jwt.decode(
                    token,
                    key=public_key,
                    algorithms=["RS256"],
                    options={"verify_aud": False},
                )
            except jwt.ExpiredSignatureError:
                raise
            except Exception as e:
                logger.exception("JWT verification failed during jwt.decode")
                raise JWTError(f"Invalid token signature: {e}")

            return payload
        except jwt.ExpiredSignatureError:
            raise JWTError("Token has expired")
        except Exception as e:
            raise JWTError(f"Invalid token: {e}")

    def get_or_create_user(self, token_claims: Dict) -> UserResponse:
        """Get or create a `UserDB` row from token claims (synchronous)."""
        neon_sub = token_claims.get("sub")
        email = token_claims.get("email")
        neon_role = token_claims.get("role", "user")

        # Validate required claims before any DB operations
        if not neon_sub or not email:
            logger.error(
                "Token claims missing required fields: sub=%s email=%s", neon_sub, email
            )
            raise JWTError("Missing required token claims: 'sub' and 'email'")

        tier = self.map_role_to_tier(neon_role)

        user = self.db.query(User).filter(User.neon_user_id == neon_sub).first()
        if user:
            # Extract actual value from SQLAlchemy Column
            current_tier = self._get_tier_value(user.subscription_tier)
            if current_tier != self._get_tier_value(tier):
                # Type: ignore because SQLAlchemy column assignment requires runtime behavior
                user.subscription_tier = tier  # type: ignore
                self.db.commit()
                self.db.refresh(user)
            return UserResponse(
                id=UUID(str(user.id)),
                email=str(user.email),
                full_name=str(getattr(user, "full_name", "") or ""),
                subscription_tier=self._get_tier_value(user.subscription_tier),
                created_at=user.created_at if isinstance(user.created_at, datetime) else datetime.utcnow(),
            )

        user = User(
            email=token_claims.get("email"),
            full_name=token_claims.get("name", ""),
            neon_user_id=neon_sub,
            subscription_tier=tier,
            hashed_password="!oauth:neon",  # Sentinel indicating OAuth-created user (no password)
            is_active=True,
            created_at=datetime.utcnow(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return UserResponse(
            id=UUID(str(user.id)),
            email=str(user.email),
            full_name=str(getattr(user, "full_name", "") or ""),
            subscription_tier=self._get_tier_value(user.subscription_tier),
            created_at=user.created_at if isinstance(user.created_at, datetime) else datetime.utcnow(),
        )

    def enforce_tier_access(self, user: UserResponse, required_tier: str = "pro") -> bool:
        if required_tier == "pro":
            if user.subscription_tier != "pro":
                raise Exception("User must upgrade to pro tier to access this resource")
        return True

    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return None
        return UserResponse(
            id=UUID(str(user.id)),
            email=str(user.email),
            full_name=str(getattr(user, "full_name", "") or ""),
            subscription_tier=self._get_tier_value(user.subscription_tier),
            created_at=user.created_at if isinstance(user.created_at, datetime) else datetime.utcnow(),
        )

    def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        user = self.db.query(User).filter(User.neon_user_id == user_id).first()
        if not user:
            return None
        return UserResponse(
            id=UUID(str(user.id)),
            email=str(user.email),
            full_name=str(getattr(user, "full_name", "") or ""),
            subscription_tier=self._get_tier_value(user.subscription_tier),
            created_at=user.created_at if isinstance(user.created_at, datetime) else datetime.utcnow(),
        )
