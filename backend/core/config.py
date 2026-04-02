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
    frontend_url: str = Field("http://localhost:3000", alias="FRONTEND_URL")
    
    # Dodo Payments
    dodo_api_key: Optional[str] = Field(None, alias="DODO_API_KEY")
    dodo_webhook_secret: Optional[str] = Field(None, alias="DODO_WEBHOOK_SECRET")
    dodo_api_url: str = "https://api.dodopayments.com"
    
    # Environment
    environment: str = "development"  # development, staging, production
    debug: bool = False
    
    # LangSmith Observability
    langchain_tracing_v2: bool = Field(False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: Optional[str] = Field(None, alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field("consilience-dev", alias="LANGCHAIN_PROJECT")
    langchain_endpoint: str = Field("https://api.smith.langchain.com", alias="LANGCHAIN_ENDPOINT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
