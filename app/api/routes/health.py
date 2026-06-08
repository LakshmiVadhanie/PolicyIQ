"""
PolicyIQ — Health Check Route
"""
from fastapi import APIRouter
from app.api.models import HealthResponse
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Infrastructure"])
async def health_check():
    """Cloud Run health probe endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.app_env,
    )


@router.get("/", tags=["Infrastructure"])
async def root():
    return {
        "service": "PolicyIQ",
        "description": "Agentic Insurance Intelligence Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
