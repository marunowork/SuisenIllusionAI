"""
Health Check API

設計書 16章「Health Check」に基づく。Docker Healthcheckから利用する。
"""

from fastapi import APIRouter

from app.schemas.image import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
