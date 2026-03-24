"""Alembic migration environment for Consilience.

Configures database connections and model tracking for schema migrations.
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our SQLAlchemy models
from backend.database.schema import Base

# Alembic Config object
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from environment (handles both sync and async URLs)
def get_sqlalchemy_url() -> str:
    """Get sync SQLAlchemy database URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please configure it in .env file"
        )
    
    # Convert async URL to sync URL for Alembic
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    # Remove query parameters that psycopg2 doesn't support
    if "?" in db_url:
        # Keep only supported parameters
        db_url = db_url.split("?")[0]
    
    return db_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    Configures context with just a URL (no Engine required).
    Good for generating migration scripts without database connection.
    """
    url = get_sqlalchemy_url()
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    
    Creates an Engine and associates connection with context.
    Used for actual database schema updates.
    """
    url = get_sqlalchemy_url()
    
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
