"""
Consilience API - Main FastAPI Application
Multi-agent research orchestration platform
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio
import logging

from core.config import get_settings
from database.connection import (
    init_async_db,
    close_db,
    get_async_session
)
from api.dependencies import get_optional_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Multi-agent research orchestration platform",
    version=settings.app_version,
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup and shutdown events

async def validate_production_config():
    """Validate production configuration on startup.
    
    CRITICAL: DEBUG must not be enabled in production environments.
    This handler runs before database initialization to fail fast.
    """
    if settings.environment.lower() == "production" and settings.debug:
        error_msg = (
            "SECURITY FAILURE: DEBUG mode is enabled in PRODUCTION environment!\n"
            "Set DEBUG=false in .env file before deploying to production.\n"
            "DEBUG mode disables JWT signature validation which is unacceptable in production.\n"
            "Application startup aborted."
        )
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    
    if settings.debug:
        logger.warning(
            f"DEBUG mode is ENABLED in {settings.environment.upper()} environment. "
            "This disables JWT signature validation. Use only for development/testing."
        )


@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup."""
    logger.info(f"{settings.app_name} API initializing...")
    
    # Validate production config first (fail fast)
    try:
        await validate_production_config()
    except RuntimeError as e:
        logger.error(f"Production configuration validation failed: {str(e)}")
        raise
    
    try:
        # Initialize async database
        await init_async_db()
        logger.info("Database initialized and connected.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down...")
    await close_db()


# Health check endpoint
@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_optional_user)
):
    """
    Health check endpoint.
    Verifies API and database connectivity.
    """
    db_status = "unreachable"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Health check failed to connect to DB: {str(e)}")

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": db_status,
        "authenticated": current_user is not None
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "status": "online",
        "service": settings.app_name,
        "version": settings.app_version,
        "documentation": "/docs",
        "health": "/health"
    }


# Include routes
from api.routes import research, auth
# from api.routes import payments  # TODO: Implement Stripe integration

app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
# app.include_router(payments.router, prefix="/api/payments", tags=["payments"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

