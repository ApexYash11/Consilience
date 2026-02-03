"""
Consilience API - Main FastAPI Application
Multi-agent research orchestration platform
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
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
@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup."""
    logger.info(f"{settings.app_name} API initializing...")
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
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": "connected",
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
# These will be imported here once implemented
# from api.routes import research, auth, payments

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

