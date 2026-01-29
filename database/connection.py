"""Database connection utilities (Neon/Postgres-ready).
Provides `get_session()` and `init_db()` helpers.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Neon/Postgres connection string
# Format: postgresql://user:password@host/dbname?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback for local development if needed, but we target Neon
    DATABASE_URL = "sqlite:///./consilience.db"

_engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from database import schema

    schema.Base.metadata.create_all(bind=_engine)
