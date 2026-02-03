"""
Configuration and settings for Consilience API.
Loads environment variables from .env file.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # Neon Auth
    auth_url: Optional[str] = Field(None, alias="AUTH_URL")
    jwks_url: Optional[str] = Field(None, alias="JWKS_URL")
    
    # OpenRouter API
    openrouter_api_key: Optional[str] = Field(None, alias="OPENROUTER_API_KEY")
    
    # App Settings
    app_name: str = "Consilience"
    app_version: str = "1.0.0"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    
    # Stripe
    stripe_secret_key: Optional[str] = Field(None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(None, alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: Optional[str] = Field(None, alias="STRIPE_WEBHOOK_SECRET")
    
    # Environment
    environment: str = "development"  # development, staging, production
    debug: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
