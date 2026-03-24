"""Auth routes for user registration, login, and email verification."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ...models.user import UserCreate, UserLogin, UserResponse, TokenResponse
from ...services.auth_service import AuthService
from ...database.connection import get_db_session
from ...config.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# Get global settings instance
_settings = Settings()


def get_auth_service(db: Session = Depends(get_db_session)) -> AuthService:
    """Dependency to provide AuthService instance."""
    return AuthService(db, _settings)


# ===== Request/Response Models =====

class VerifyEmailRequest(BaseModel):
    """Email verification request."""
    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""
    email: EmailStr


class VerificationResponse(BaseModel):
    """Verification response."""
    success: bool
    message: str


# ===== Auth Endpoints =====

@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    """
    Register a new user account.
    
    Validates password strength, checks for duplicate emails,
    creates user in database with hashed password, and sends verification email.
    
    Args:
        user_data: Registration data (email, password, full_name)
        
    Returns:
        UserResponse with newly created user
        
    Raises:
        HTTPException 400: Invalid password or duplicate email
    """
    try:
        user = service.register_user(user_data)
        return user
    except ValueError as e:
        logger.warning(f"Registration validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLogin,
    service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """
    Authenticate user with email and password.
    
    Validates credentials against database, generates JWT token.
    
    Args:
        credentials: Login credentials (email, password)
        
    Returns:
        TokenResponse with access token
        
    Raises:
        HTTPException 401: Invalid credentials
        HTTPException 400: Account inactive
    """
    try:
        user_token = service.authenticate_user(credentials)
        if not user_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        return user_token
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error in login: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/verify-email", response_model=VerificationResponse)
def verify_email(
    request: VerifyEmailRequest,
    service: AuthService = Depends(get_auth_service)
) -> VerificationResponse:
    """
    Verify user email with verification token.
    
    Args:
        request: Verification request with token
        
    Returns:
        VerificationResponse with success status
        
    Raises:
        HTTPException 400: Invalid or expired token
    """
    success, message = service.verify_email(request.token)
    
    status_code = 200 if success else 400
    if not success:
        raise HTTPException(status_code=status_code, detail=message)
    
    return VerificationResponse(success=success, message=message)


@router.post("/resend-verification", response_model=VerificationResponse)
def resend_verification(
    request: ResendVerificationRequest,
    service: AuthService = Depends(get_auth_service)
) -> VerificationResponse:
    """
    Resend email verification to user.
    
    Args:
        request: Resend request with email
        
    Returns:
        VerificationResponse with success status
        
    Note:
        Always returns 200 for security (doesn't reveal if email exists)
    """
    try:
        success, message = service.resend_verification_email(request.email)
    except Exception as e:
        logger.exception(f"Error resending verification email: {type(e).__name__}")
        success = False
        message = "If email exists, verification email will be sent"
    
    return VerificationResponse(success=success, message=message)
