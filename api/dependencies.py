"""
Dependency injection for FastAPI endpoints.
Provides authenticated user context and database sessions.
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_security_manager, extract_bearer_token
from database.connection import get_async_session
from models.user import CurrentUser
from models.research import ResearchDepth
from services.cost_service import CostService
from services.rate_limiter import get_rate_limiter

async def get_db() -> AsyncGenerator[AsyncSession, None]:  # type: ignore
    """
    Dependency to get database session for async operations.
    Provides an AsyncSession that can be used in endpoints.
    """
    async for session in get_async_session():
        yield session


async def get_current_user(
    authorization: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    """
    Dependency to get current authenticated user.

    Validates the Neon JWT token from Authorization header and returns
    user context with ID, email, tier, and roles.

    Args:
        authorization: Authorization header with Bearer token
        db: Database session (asyncio)

    Returns:
        CurrentUser object with user_id, email, tier, roles

    Raises:
        HTTPException: 401 if token is invalid or missing
    """
    # Extract and validate token
    token = extract_bearer_token(authorization)
    security_mgr = get_security_manager()

    # Verify JWT signature and claims
    payload = await security_mgr.verify_token(token)

    # Extract user info
    user_info = security_mgr.extract_user_info(payload)

    # Create current user object
    current_user = CurrentUser(
        user_id=user_info["user_id"],
        email=user_info["email"],
        tier=user_info["tier"],
        roles=user_info["roles"],
    )

    return current_user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[CurrentUser]:
    """
    Dependency for optional authentication.
    Returns user if token provided, None otherwise.
    """
    if not authorization:
        return None

    try:
        token = extract_bearer_token(authorization)
        security_mgr = get_security_manager()
        payload = await security_mgr.verify_token(token)
        user_info = security_mgr.extract_user_info(payload)

        return CurrentUser(
            user_id=user_info["user_id"],
            email=user_info["email"],
            tier=user_info["tier"],
            roles=user_info["roles"],
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise exc


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
    from services.cost_service import CostService
    from models.research import ResearchDepth

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
    from services.cost_service import CostService
    from models.research import ResearchDepth

    try:
        await CostService().check_quota(current_user.user_id, ResearchDepth.DEEP)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )
    return current_user


async def check_rate_limit(
    current_user: CurrentUser = Depends(get_current_user),
    max_requests: int = 10,
    window_seconds: int = 60,
) -> CurrentUser:
    """
    Dependency to enforce per-user rate limiting on research endpoints.
    Default: 10 requests per minute per user.

    Raises:
        HTTPException: 429 if user exceeds rate limit
    """
    limiter = get_rate_limiter()

    # Check if user is rate limited
    if limiter.is_rate_limited(current_user.user_id, max_requests, window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds",
        )

    # Record this request
    limiter.add_request(current_user.user_id)

    return current_user
