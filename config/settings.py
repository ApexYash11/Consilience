"""Environment configuration for Consilience.
Loads values from environment variables and .env file.
"""
from pydantic import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Consilience"
    DEBUG: bool = True
    # Neon/Postgres connection string
    DATABASE_URL: str | None = None

    # Stripe
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
