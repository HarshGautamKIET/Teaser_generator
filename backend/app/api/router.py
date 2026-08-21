"""Aggregates all route modules under the /api prefix."""

from fastapi import APIRouter

from app.api.routes import health, jobs, media, videos

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(jobs.router)
api_router.include_router(media.router)
api_router.include_router(videos.router)
