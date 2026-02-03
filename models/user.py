"""
Pydantic models for user-related API requests/responses and authentication.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID, uuid4


class CurrentUser(BaseModel):
    """Current authenticated user context."""
    user_id: str
    email: str
    tier: str  # "free" or "paid"
    roles: List[str] = Field(default_factory=list)


class UserBase(BaseModel):
    """Base user model."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """User creation model."""
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User response model."""
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    subscription_tier: str = "free"
    created_at: datetime
    class Config:
        from_attributes = True


class UserTierResponse(BaseModel):
    """User tier and quota information."""
    user_id: str
    email: str
    subscription_tier: str
    monthly_standard_quota: int
    monthly_deep_quota: int
    current_standard_usage: int
    current_deep_usage: int

