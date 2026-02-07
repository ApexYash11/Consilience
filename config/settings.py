"""Environment configuration for Consilience.
Loads values from environment variables and .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Consilience"
    DEBUG: bool = True
    # Neon/Postgres connection string
    DATABASE_URL: str | None = None

    # Neon Auth
    AUTH_URL: str | None = None
    JWKS_URL: str | None = None

    # OpenRouter API
    OPENROUTER_API_KEY: str | None = None

    # Stripe
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


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
