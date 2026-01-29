"""Auth routes for user registration and login."""
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import UserCreate, UserLogin, UserResponse, TokenResponse
from services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, service: AuthService = Depends()):
    """Register a new user account."""
    try:
        user = service.register_user(user_data)
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, service: AuthService = Depends()):
    """Authenticate and get access token."""
    user_token = service.authenticate_user(credentials)
    if not user_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return user_token
