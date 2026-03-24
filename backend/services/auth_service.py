"""Authentication service logic with password hashing and JWT token generation."""

import re
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..models.user import UserCreate, UserLogin, UserResponse, TokenResponse
from ..models.payment import SubscriptionTier, SubscriptionStatus
from ..database.schema import UserDB, EmailVerificationDB
from ..config.settings import Settings
from .email_service import EmailService


class AuthService:
    """Handles user registration, authentication, password management, and JWT tokens."""
    
    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REGEX = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    )
    PASSWORD_PATTERN_ERROR = (
        "Password must be at least 8 characters and contain "
        "uppercase, lowercase, number, and special character (@$!%*?&)"
    )
    
    # JWT configuration (hardcoded, can be moved to settings)
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    
    def __init__(self, db_session: Session, settings: Settings):
        """Initialize auth service with database session and settings."""
        self.db = db_session
        self.settings = settings
        
        # Generate JWT secret from settings or fallback to default (for dev only)
        self.jwt_secret = getattr(settings, 'JWT_SECRET', 'change-me-in-production')
        if self.jwt_secret == 'change-me-in-production' and not settings.DEBUG:
            raise RuntimeError(
                "JWT_SECRET not configured! Set JWT_SECRET in environment variables. "
                "In production, this must be a secure random string."
            )
    
    # ===== Password Management =====
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt with 12 rounds (production-grade security)."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against bcrypt hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except (ValueError, TypeError):
            # Invalid hash format or encoding issues
            return False
    
    def validate_password_strength(self, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password meets security requirements.
        
        Returns:
            (is_valid, error_message)
            - is_valid: True if password meets requirements
            - error_message: None if valid, otherwise descriptive error
        """
        if len(password) < self.PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters"
        
        if not self.PASSWORD_REGEX.match(password):
            return False, self.PASSWORD_PATTERN_ERROR
        
        return True, None
    
    # ===== JWT Token Management =====
    
    def generate_token(self, user_id: str, email: str, tier: str = "free") -> str:
        """
        Generate JWT access token for authenticated user.
        
        Args:
            user_id: UUID of the user
            email: User's email address
            tier: Subscription tier (free/pro)
            
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        payload = {
            "sub": str(user_id),  # Subject (user ID)
            "email": email,
            "tier": tier,
            "iat": now,  # Issued at
            "exp": now + timedelta(hours=self.JWT_EXPIRATION_HOURS),  # Expiration
            "type": "access"
        }
        
        token = jwt.encode(
            payload,
            self.jwt_secret,
            algorithm=self.JWT_ALGORITHM
        )
        
        return token
    
    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload if valid, None if invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    # ===== Email Verification =====
    
    def create_verification_token(self, user_id: str, email: str) -> str:
        """
        Create and store email verification token.
        
        Args:
            user_id: UUID of the user
            email: User's email address
            
        Returns:
            Verification token string
        """
        # Remove old verification token if exists
        old_token = self.db.execute(
            select(EmailVerificationDB).where(EmailVerificationDB.user_id == user_id)
        ).scalar_one_or_none()
        
        if old_token:
            self.db.delete(old_token)
        
        # Create new verification token
        token = EmailService.generate_verification_token()
        verification = EmailVerificationDB(
            user_id=user_id,
            email=email,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=EmailService.VERIFICATION_EXPIRY_HOURS),
            last_sent_at=datetime.utcnow()
        )
        
        self.db.add(verification)
        self.db.commit()
        
        return token
    
    def verify_email(self, token: str) -> tuple[bool, str]:
        """
        Verify email with token.
        
        Args:
            token: Email verification token
            
        Returns:
            (success, message)
            - success: True if verification successful
            - message: Status message
        """
        # Find verification record
        verification = self.db.execute(
            select(EmailVerificationDB).where(EmailVerificationDB.token == token)
        ).scalar_one_or_none()
        
        if not verification:
            return False, "Invalid verification token"
        
        if verification.is_expired():
            return False, "Verification token has expired"
        
        if verification.verified_at:  # type: ignore
            return False, "Email already verified"
        
        # Mark user as verified
        user = self.db.execute(
            select(UserDB).where(UserDB.id == verification.user_id)
        ).scalar_one_or_none()
        
        if not user:
            return False, "User not found"
        
        user.is_verified = True  # type: ignore
        verification.verified_at = datetime.utcnow()  # type: ignore
        self.db.commit()
        
        return True, "Email verified successfully"
    
    def resend_verification_email(self, email: str) -> tuple[bool, str]:
        """
        Resend verification email to user.
        
        Args:
            email: User's email address
            
        Returns:
            (success, message)
        """
        # Find user and verification record
        user = self.db.execute(
            select(UserDB).where(UserDB.email == email)
        ).scalar_one_or_none()
        
        if not user:
            # Don't reveal if email exists (security best practice)
            return True, "If email exists, verification email will be sent"
        
        if user.is_verified:  # type: ignore
            return False, "Email is already verified"
        
        # Get or create verification token
        verification = self.db.execute(
            select(EmailVerificationDB).where(EmailVerificationDB.user_id == user.id)
        ).scalar_one_or_none()
        
        if not verification:
            # Create new verification if doesn't exist
            token = self.create_verification_token(str(user.id), user.email)  # type: ignore
        else:
            # Generate a fresh token for resend instead of reusing the old one
            token = EmailService.generate_verification_token()
            verification.token = token  # type: ignore
            verification.last_sent_at = datetime.utcnow()  # type: ignore
            verification.expires_at = datetime.utcnow() + timedelta(hours=EmailService.VERIFICATION_EXPIRY_HOURS)  # type: ignore
            self.db.commit()
        
        # Send email
        EmailService.send_verification_email(user.email, token)  # type: ignore
        
        return True, "Verification email sent"
    
    # ===== User Registration =====
    
    def register_user(self, user_data: UserCreate) -> UserResponse:
        """
        Register a new user with email and password.
        
        Args:
            user_data: Registration data (email, password, full_name)
            
        Returns:
            UserResponse with newly created user
            
        Raises:
            ValueError: If email already exists or password is invalid
        """
        # Validate password strength
        is_valid, error_msg = self.validate_password_strength(user_data.password)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Check if email already exists
        existing_user = self.db.execute(
            select(UserDB).where(UserDB.email == user_data.email)
        ).scalar_one_or_none()
        
        if existing_user:
            # Don't reveal that email exists (security best practice - anti-enumeration)
            raise ValueError("Unable to create account")
        
        # Hash password
        hashed_password = self.hash_password(user_data.password)
        
        # Create user in database
        new_user = UserDB(
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            subscription_tier=SubscriptionTier.FREE,
            subscription_status=SubscriptionStatus.ACTIVE,
            is_active=True,
            is_verified=False,  # Email verification pending
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        
        # Create and send verification email
        verification_token = self.create_verification_token(str(new_user.id), new_user.email)  # type: ignore
        EmailService.send_verification_email(new_user.email, verification_token)  # type: ignore
        
        # Return user response
        return UserResponse(
            id=new_user.id,  # type: ignore
            email=new_user.email,  # type: ignore
            full_name=new_user.full_name,  # type: ignore
            subscription_tier=new_user.subscription_tier.value,
            created_at=new_user.created_at  # type: ignore
        )
    
    # ===== User Authentication =====
    
    def authenticate_user(self, credentials: UserLogin) -> Optional[TokenResponse]:
        """
        Authenticate user with email and password.
        
        Args:
            credentials: Login credentials (email, password)
            
        Returns:
            TokenResponse with access token if authentication succeeds
            None if email not found or password incorrect
        """
        # Look up user by email
        user = self.db.execute(
            select(UserDB).where(UserDB.email == credentials.email)
        ).scalar_one_or_none()
        
        if not user:
            return None
        
        # Skip authentication for OAuth users (they have special sentinel value)
        if user.hashed_password == "!oauth:neon":  # type: ignore
            return None
        
        # Verify password
        if not self.verify_password(credentials.password, user.hashed_password):  # type: ignore
            return None
        
        # Check if user is active - return None instead of raising to avoid leaking account state
        if not user.is_active:  # type: ignore
            return None
        
        # Update last login timestamp
        user.last_login = datetime.utcnow()  # type: ignore
        self.db.commit()
        
        # Generate JWT token
        access_token = self.generate_token(
            user_id=user.id,  # type: ignore
            email=user.email,  # type: ignore
            tier=user.subscription_tier.value
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.JWT_EXPIRATION_HOURS * 3600  # Convert hours to seconds
        )
