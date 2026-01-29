"""User-related Pydantic models."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID, uuid4
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str]


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    full_name: Optional[str]
    subscription_tier: str = "free"
    created_at: datetime = Field(default_factory=datetime.utcnow)

