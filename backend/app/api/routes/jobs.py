"""Job status and control routes."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth import AuthUser, get_current_user
from app.errors import NotFoundError
from app.schemas import JobListResponse, JobResponse
from app.services import generation_service
from app.storage import GENERATED, Storage, get_storage

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


@router.get("/{job_id}/preview/media")
async def get_preview_media(
    job_id: str,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> FileResponse:
    """Stream a run's assembled preview to its owner.

    Resolved through the caller's own RLS-scoped session, like teaser media: a
    run belonging to someone else is not found rather than forbidden.
    """
    job = generation_service.get_job(db, job_id)
    if not job.preview_storage_key:
        raise NotFoundError(
            "PREVIEW_NOT_FOUND", f"Run {job_id} did not produce a preview."
        )

    path = storage.resolve(GENERATED, job.preview_storage_key)
    if not path.is_file():
        raise NotFoundError(
            "PREVIEW_MEDIA_MISSING",
            f"The preview file for run {job_id} is no longer on disk.",
        )
    return FileResponse(path, media_type="video/mp4", filename="preview.mp4")


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> JobResponse:
    """Stop a running job.

    The session is already scoped to the caller, so someone else's job is not
    "forbidden" here -- it simply is not found, and leaks nothing about whether
    the id exists.
    """
    return JobResponse.from_model(generation_service.cancel_job(db, job_id))
