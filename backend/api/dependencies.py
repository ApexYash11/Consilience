"""
Dependency injection for FastAPI endpoints.
Provides authenticated user context and database sessions.
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import extract_bearer_token
from ..database.connection import get_async_session, get_db_session
from ..models.user import CurrentUser
from ..models.research import ResearchDepth
from ..services.cost_service import CostService
from ..services.rate_limiter import get_rate_limiter
from ..services.auth_service import AuthService
from ..config.settings import Settings

async def get_db() -> AsyncGenerator[AsyncSession, None]:  # type: ignore
    """
    Dependency to get database session for async operations.
    Provides an AsyncSession that can be used in endpoints.
    """
    async for session in get_async_session():
        yield session


async def get_current_user(
    authorization: Optional[str] = Header(None), db = Depends(get_db_session)
) -> CurrentUser:
    """
    Dependency to get current authenticated user.

    Validates the JWT token from Authorization header (email/password login)
    and returns user context with ID, email, tier, and roles.

    Args:
        authorization: Authorization header with Bearer token
        db: Database session for user lookup if needed

    Returns:
        CurrentUser object with user_id, email, tier, roles

    Raises:
        HTTPException: 401 if token is invalid or missing
    """
    # Extract bearer token
    token = extract_bearer_token(authorization)
    
    # Initialize AuthService and verify token
    settings = Settings()
    auth_service = AuthService(db, settings)
    
    # Verify JWT and get payload
    payload = auth_service.verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Extract user info from payload
    user_id = payload.get("sub")
    email = payload.get("email")
    tier = payload.get("tier", "free")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Create current user object
    current_user = CurrentUser(
        user_id=user_id,
        email=email,
        tier=tier,
        roles=[]  # AuthService tokens don't include roles
    )
    
    return current_user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    db = Depends(get_db_session)
) -> Optional[CurrentUser]:
    """
    Dependency for optional authentication.
    Returns user if token provided, None otherwise.
    """
    if not authorization:
        return None

    try:
        token = extract_bearer_token(authorization)
        
        # Initialize AuthService and verify token
        settings = Settings()
        auth_service = AuthService(db, settings)
        
        # Verify JWT and get payload
        payload = auth_service.verify_token(token)
        
        if payload is None:
            return None
        
        # Extract user info from payload
        user_id = payload.get("sub")
        email = payload.get("email")
        tier = payload.get("tier", "free")
        
        if not user_id or not email:
            return None
        
        return CurrentUser(
            user_id=user_id,
            email=email,
            tier=tier,
            roles=[]  # AuthService tokens don't include roles
        )
    except Exception:
        return None


async def require_paid_tier(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency to enforce paid subscription tier.
    Use on endpoints that are premium-only (e.g., deep research).

    Raises:
        HTTPException: 403 if user is on free tier
    """
    if current_user.tier != "paid":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a paid subscription",
        )
    return current_user


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency to enforce admin role.

    Raises:
        HTTPException: 403 if user is not admin
    """
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return current_user


async def check_standard_quota(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency to enforce standard research monthly quota.
    Raises HTTP 429 if the user has used their monthly allowance.
    """
    from ..services.cost_service import CostService
    from ..models.research import ResearchDepth

    try:
        await CostService().check_quota(current_user.user_id, ResearchDepth.STANDARD)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )
    return current_user


async def check_deep_quota(
    current_user: CurrentUser = Depends(require_paid_tier),
) -> CurrentUser:
    """
    Dependency to enforce deep research monthly quota.
    Combines paid-tier check + quota enforcement.
    Raises HTTP 429 if the user has used their deep research allowance.
    """
    from ..services.cost_service import CostService
    from ..models.research import ResearchDepth

    try:
        await CostService().check_quota(current_user.user_id, ResearchDepth.DEEP)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )
    return current_user


def check_rate_limit_factory(
    max_requests: int = 10, window_seconds: int = 60
):
    """
    Factory function to create a configurable rate limit dependency.
    
    Args:
        max_requests: Maximum requests allowed in the time window
        window_seconds: Time window in seconds
    
    Returns:
        An async dependency that checks and enforces rate limits
    
    Example:
        @app.post("/api/research/standard")
        async def create_research(
            current_user: CurrentUser = Depends(check_rate_limit_factory(max_requests=10, window_seconds=60))
        ):
            ...
    """
    async def rate_limit_check(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        """
        Dependency to enforce per-user rate limiting on research endpoints.

        Raises:
            HTTPException: 429 if user exceeds rate limit
        """
        limiter = get_rate_limiter()

        # Atomically check and record the request (check_and_record is synchronous)
        allowed = limiter.check_and_record(
            current_user.user_id, max_requests, window_seconds
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds",
            )

        return current_user

    return rate_limit_check


async def check_rate_limit(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Default rate limit dependency (10 requests per 60 seconds).
    
    For custom limits, use: Depends(check_rate_limit_factory(max_requests, window_seconds))
    """
    limiter = get_rate_limiter()

    # Use atomic check_and_record instead of separate is_rate_limited + add_request
    allowed = limiter.check_and_record(current_user.user_id, max_requests=10, window_seconds=60)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: 10 requests per 60 seconds",
        )

    return current_user
