"""OAuth callback routes for Google and GitHub authentication."""
import logging
from fastapi import APIRouter, Query, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...config.settings import Settings
from ...database.connection import get_db_session
from ...services.oauth_service import OAuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"], prefix="/oauth")

# Get settings
_settings = Settings()


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request from frontend."""
    code: str
    provider: str  # 'google' or 'github'


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


async def get_oauth_service(db: Session = Depends(get_db_session)) -> OAuthService:
    """Dependency to provide OAuthService instance."""
    return OAuthService(db, _settings)


@router.post("/callback", response_model=TokenResponse)
async def oauth_callback(
    request: OAuthCallbackRequest,
    service: OAuthService = Depends(get_oauth_service),
) -> TokenResponse:
    """
    Handle OAuth callback from frontend.
    
    Frontend calls this endpoint after user authorizes via Google/GitHub dialog.
    Exchanges auth code for access token and returns JWT.
    
    Expected flow:
    1. Frontend redirects user to Google/GitHub login
    2. User authorizes app
    3. Redirects back to frontend with `code` parameter
    4. Frontend calls this endpoint with code + provider
    5. Backend exchanges code for access token
    6. Backend gets user info and creates/retrieves user
    7. Returns JWT token for authenticated requests
    """
    if request.provider not in ["google", "github"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {request.provider}",
        )

    try:
        if request.provider == "google":
            return await _handle_google_callback(request.code, service)
        else:
            return await _handle_github_callback(request.code, service)
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes
        raise
    except Exception as e:
        logger.error(f"OAuth callback failed for {request.provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed",
        )


async def _handle_google_callback(code: str, service: OAuthService) -> TokenResponse:
    """Handle Google OAuth callback."""
    # Exchange code for token
    token_response = await service.get_google_token(code)
    if not token_response or "access_token" not in token_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to exchange Google code",
        )

    # Get user info
    access_token = token_response["access_token"]
    user_info = await service.get_google_user_info(access_token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to get user info from Google",
        )

    # Create or get user
    email = user_info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not provided by Google",
        )
    
    name = user_info.get("name") or email.split("@")[0]
    provider_id = user_info.get("id")
    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provider ID not provided by Google",
        )

    user = service.get_or_create_oauth_user(
        email=email,
        full_name=name,
        provider="google",
        provider_id=str(provider_id),
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account",
        )

    # Generate JWT token
    jwt_token = service.generate_oauth_jwt_token(user)
    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate token",
        )

    logger.info(f"Google OAuth successful for user {user.id}")
    return TokenResponse(access_token=jwt_token)


async def _handle_github_callback(code: str, service: OAuthService) -> TokenResponse:
    """Handle GitHub OAuth callback."""
    # Exchange code for token
    token_response = await service.get_github_token(code)
    if not token_response or "access_token" not in token_response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to exchange GitHub code",
        )

    # Get user info
    access_token = token_response["access_token"]
    user_info = await service.get_github_user_info(access_token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to get user info from GitHub",
        )

    # Get email: fetch from /user/emails endpoint if not in user_info
    login = user_info.get("login")
    email = user_info.get("email")
    
    if not email:
        # Fetch verified email from GitHub's /user/emails endpoint
        try:
            email = await service.get_github_verified_email(access_token)
        except Exception as e:
            logger.warning(f"Failed to fetch GitHub verified email: {e}")
            email = None
    
    # If no email found, log but allow creation with None email if login exists
    if not email:
        if not login:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to retrieve email or login from GitHub account",
            )
        # log the situation
        logger.warning(f"GitHub user {login} has no verified email, will create with null")
    
    name = user_info.get("name") or login or "GitHub User"
    provider_id = user_info.get("id")
    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provider ID not provided by GitHub",
        )

    user = service.get_or_create_oauth_user(
        email=email,
        full_name=name,
        provider="github",
        provider_id=str(provider_id),
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account",
        )

    # Generate JWT token
    jwt_token = service.generate_oauth_jwt_token(user)
    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate token",
        )

    logger.info(f"GitHub OAuth successful for user {user.id}")
    return TokenResponse(access_token=jwt_token)


@router.get("/authorize/google")
def get_google_auth_url(state: str | None = None):
    """Get Google OAuth authorization URL."""
    if not _settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured",
        )
    
    # Validate redirect URI is configured
    if not _settings.GOOGLE_REDIRECT_URI:
        logger.error("GOOGLE_REDIRECT_URI is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth redirect URI not configured on server",
        )

    from urllib.parse import urlencode
    import secrets

    # If no state provided, generate one
    if not state:
        state = secrets.token_urlsafe(32)

    params = {
        "client_id": _settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid profile email",
        "access_type": "offline",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"auth_url": auth_url, "state": state}


@router.get("/authorize/github")
def get_github_auth_url(state: str | None = None):
    """Get GitHub OAuth authorization URL."""
    if not _settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured",
        )
    
    # Validate redirect URI is configured
    if not _settings.GITHUB_REDIRECT_URI:
        logger.error("GITHUB_REDIRECT_URI is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth redirect URI not configured on server",
        )

    from urllib.parse import urlencode
    import secrets

    # If no state provided, generate one
    if not state:
        state = secrets.token_urlsafe(32)

    params = {
        "client_id": _settings.GITHUB_CLIENT_ID,
        "redirect_uri": _settings.GITHUB_REDIRECT_URI,
        "scope": "user:email",
        "allow_signup": "true",
        "state": state,
    }
    auth_url = "https://github.com/login/oauth/authorize?" + urlencode(params)
    return {"auth_url": auth_url, "state": state}
