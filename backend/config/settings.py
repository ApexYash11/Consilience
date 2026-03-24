"""Environment configuration for Consilience.
Loads values from environment variables and .env file.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "Consilience"
    DEBUG: bool = False  # SECURITY: Must be False in production; only True for testing
    BASE_URL: Optional[str] = None  # e.g., https://example.com for production
    
    # Neon/Postgres connection string
    DATABASE_URL: str | None = None

    # Neon Auth
    AUTH_URL: str | None = None
    JWKS_URL: str | None = None

    # JWT Token Generation (for username/password auth)
    JWT_SECRET: str | SecretStr = "change-me-in-production"  # SECURITY: Override in production
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # GitHub OAuth
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: SecretStr | None = None
    GITHUB_REDIRECT_URI: Optional[str] = None

    # Backend OAuth Redirect
    BACKEND_OAUTH_CALLBACK_URL: Optional[str] = None

    # OpenRouter API
    OPENROUTER_API_KEY: Optional[SecretStr] = None

    # Stripe
    STRIPE_SECRET_KEY: Optional[SecretStr] = None
    STRIPE_WEBHOOK_SECRET: Optional[SecretStr] = None

    # Anthropic / Claude
    ANTHROPIC_API_KEY: Optional[SecretStr] = None

    # LangSmith Observability
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[SecretStr] = None
    LANGCHAIN_PROJECT: str = "consilience-dev"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("JWT_SECRET", mode="after")
    @classmethod
    def validate_jwt_secret(cls, v: str | SecretStr) -> str | SecretStr:
        """Validate JWT_SECRET format and preserve SecretStr type.
        
        Note: Enforcement of non-default values for production is handled
        in model_post_init which checks DEBUG flag.
        """
        # Simply return the value - SecretStr handling is preserved
        return v

    @field_validator("GOOGLE_REDIRECT_URI", mode="before")
    @classmethod
    def validate_google_redirect_uri(cls, v: Optional[str], info) -> Optional[str]:
        """Set GOOGLE_REDIRECT_URI from BASE_URL if not explicitly set."""
        if v is not None:
            return v
        # If BASE_URL is set, derive redirect_uri from it (normalize trailing slashes)
        base_url = info.data.get("BASE_URL")
        if base_url:
            return f"{base_url.rstrip('/')}/api/oauth/google/callback"
        # Default for development
        return "http://localhost:8000/api/oauth/google/callback"

    @field_validator("GITHUB_REDIRECT_URI", mode="before")
    @classmethod
    def validate_github_redirect_uri(cls, v: Optional[str], info) -> Optional[str]:
        """Set GITHUB_REDIRECT_URI from BASE_URL if not explicitly set."""
        if v is not None:
            return v
        # If BASE_URL is set, derive redirect_uri from it (normalize trailing slashes)
        base_url = info.data.get("BASE_URL")
        if base_url:
            return f"{base_url.rstrip('/')}/api/oauth/github/callback"
        # Default for development
        return "http://localhost:8000/api/oauth/github/callback"

    @field_validator("BACKEND_OAUTH_CALLBACK_URL", mode="before")
    @classmethod
    def validate_backend_oauth_callback_url(cls, v: Optional[str], info) -> Optional[str]:
        """Set BACKEND_OAUTH_CALLBACK_URL from BASE_URL if not explicitly set."""
        if v is not None:
            return v
        # If BASE_URL is set, derive callback URL from it (normalize trailing slashes)
        base_url = info.data.get("BASE_URL")
        if base_url:
            return f"{base_url.rstrip('/')}/api/auth/oauth/callback"
        # Default for development
        return "http://localhost:8000/api/auth/oauth/callback"

    def model_post_init(self, __context=None) -> None:
        """Validate critical settings at startup (Pydantic v2 hook)."""
        # Validate JWT_SECRET is not the insecure default when DEBUG=False
        secret_value = (
            self.JWT_SECRET.get_secret_value()
            if isinstance(self.JWT_SECRET, SecretStr)
            else self.JWT_SECRET
        )
        if not self.DEBUG and secret_value == "change-me-in-production":
            raise RuntimeError(
                "JWT_SECRET must be configured in production. "
                "Set JWT_SECRET environment variable to a secure random value."
            )


class RetryConfig(BaseSettings):
    """Retry and timeout configuration for LLM calls."""

    # Timeouts
    LLM_CALL_TIMEOUT_SECONDS: int = 60  # Max duration per API call
    LLM_AGENT_TIMEOUT_SECONDS: int = 180  # Max duration per agent node

    # Retry strategy
    MAX_RETRIES: int = 3  # Maximum retry attempts
    INITIAL_RETRY_DELAY_SECONDS: float = 1.0  # Start with 1 second
    MAX_RETRY_DELAY_SECONDS: float = 30.0  # Cap at 30 seconds
    BACKOFF_MULTIPLIER: float = 2.0  # Exponential: 1s, 2s, 4s, 8s...
    JITTER_ENABLED: bool = True  # Add randomness to avoid thundering herd

    # Circuit breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5  # Fail after N consecutive errors
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS: int = 300  # Try again after 5 min

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CONSILIENCE_", extra="ignore")


settings = Settings()
retry_config = RetryConfig()
