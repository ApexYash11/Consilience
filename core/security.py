"""
Security utilities for Consilience API.
Handles Neon JWT validation, token verification, and role-based access control.
"""

import os
from typing import Optional
from datetime import datetime, timedelta
import jwt
import httpx
from functools import lru_cache
from fastapi import HTTPException, status

from core.config import get_settings


class NeonSecurityManager:
    """Manages Neon-provided JWT validation and session verification."""
    
    def __init__(self):
        self.settings = get_settings()
        self._jwks_cache = None
        self._jwks_updated_at = None
    
    async def get_jwks(self):
        """Fetch JWKS (JSON Web Key Set) from Neon auth endpoint."""
        # Cache JWKS for 24 hours
        if self._jwks_cache and self._jwks_updated_at:
            if datetime.utcnow() - self._jwks_updated_at < timedelta(hours=24):
                return self._jwks_cache
        
        if not self.settings.jwks_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWKS_URL not configured"
            )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.settings.jwks_url, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_updated_at = datetime.utcnow()
                return self._jwks_cache
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch JWKS: {str(e)}"
            )
    
    async def verify_token(self, token: str) -> dict:
        """
        Verify a Neon-issued JWT token.
        
        Args:
            token: Bearer token from Authorization header
            
        Returns:
            Decoded token payload containing user info and claims
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Decode header to get kid (key id)
            unverified = jwt.decode(token, options={"verify_signature": False})
            header = jwt.get_unverified_header(token)
            
            # Get JWKS and find the key
            jwks = await self.get_jwks()
            key = None
            for k in jwks.get("keys", []):
                if k.get("kid") == header.get("kid"):
                    key = k
                    break
            
            if not key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to find signing key"
                )
            
            # Verify token with public key
            from jwt import PyJWK
            key_obj = PyJWK.from_dict(key)
            payload = jwt.decode(
                token,
                key_obj.key,
                algorithms=["RS256"],
                audience=self.settings.database_url.split("//")[1].split(".")[0],  # Extract project from URL
            )
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
    
    def extract_user_info(self, token_payload: dict) -> dict:
        """
        Extract user information from token payload.
        
        Returns dict with:
        - user_id: Neon user ID
        - email: User email
        - roles: List of Neon roles
        - tier: Subscription tier (derived from roles)
        """
        user_id = token_payload.get("sub")
        email = token_payload.get("email")
        roles = token_payload.get("roles", [])
        
        # Determine tier from roles
        tier = "free"
        if "paid" in roles or "pro" in roles:
            tier = "paid"
        
        return {
            "user_id": user_id,
            "email": email,
            "roles": roles,
            "tier": tier,
            "token_payload": token_payload
        }


@lru_cache()
def get_security_manager() -> NeonSecurityManager:
    """Get singleton instance of security manager."""
    return NeonSecurityManager()


def extract_bearer_token(authorization: Optional[str]) -> str:
    """
    Extract bearer token from Authorization header.
    
    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")
        
    Returns:
        Token string
        
    Raises:
        HTTPException: If header is missing or malformed
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )
    
    return parts[1]
