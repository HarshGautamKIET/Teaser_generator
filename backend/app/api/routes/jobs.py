"""Job status route."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas import JobListResponse, JobResponse
from app.services import generation_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    video_id: str | None = None, db: Session = Depends(get_db)
) -> JobListResponse:
    """Runs owned by the caller, newest first. Pass `video_id` to narrow to one source."""
    return JobListResponse.from_rows(generation_service.list_jobs(db, video_id))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    """Current processing state for a job (FR-018)."""
    return JobResponse.from_model(generation_service.get_job(db, job_id))
