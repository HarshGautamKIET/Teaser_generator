"""Video routes. Thin by design -- all rules live in services."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth import AuthUser, get_current_user
from app.config import Settings, get_settings
from app.schemas import (
    GenerateRequest,
    GenerateResponse,
    TeaserListResponse,
    UrlIngestRequest,
    VideoListResponse,
    VideoResponse,
    VideoUploadResponse,
)
from app.services import (
    feedback_service,
    generation_service,
    ingest_service,
    video_service,
)
from app.services.job_runner import fetch_video_in_background, run_job_in_background
from app.storage import Storage, get_storage

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/upload", response_model=VideoUploadResponse, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> VideoUploadResponse:
    video = video_service.create_video_from_upload(
        db, storage, settings, file, user.id
    )
    return VideoUploadResponse.from_model(video)


@router.post("/from-url", response_model=VideoResponse, status_code=202)
async def create_video_from_url(
    body: UrlIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> VideoResponse:
    """Queue a fetch of a video from a URL.

    202, not 201: the row exists but the bytes do not yet. The caller polls
    GET /videos/{id} until the status leaves `fetching`.
    """
    video = ingest_service.create_video_from_url(db, body.url, user.id)
    background_tasks.add_task(fetch_video_in_background, video.id, user.id)
    return VideoResponse.from_model(video)


@router.get("", response_model=VideoListResponse)
async def list_videos(db: Session = Depends(get_db)) -> VideoListResponse:
    """Source videos owned by the caller, newest first."""
    return VideoListResponse.from_rows(video_service.list_videos(db))


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str, db: Session = Depends(get_db)
) -> VideoResponse:
    video = video_service.get_video(db, video_id)
    return VideoResponse.from_model(video)


@router.post(
    "/{video_id}/generate", response_model=GenerateResponse, status_code=202
)
async def generate_teasers(
    video_id: str,
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
) -> GenerateResponse:
    """Queue teaser generation for an audience and style (FR-004, FR-005)."""
    job = generation_service.create_job(
        db, video_id, body.audience, body.style, user.id,
        teaser_count=body.teaser_count,
        clip_max_seconds=body.clip_max_seconds,
        aspect_ratio=body.aspect_ratio,
        recording_type=body.recording_type,
        custom_prompt=body.custom_prompt,
    )
    # The worker opens its own session, so it needs the owner passed explicitly.
    background_tasks.add_task(run_job_in_background, job.id, user.id)
    return GenerateResponse.from_model(job)


@router.get("/{video_id}/teasers", response_model=TeaserListResponse)
async def list_teasers(
    video_id: str,
    job_id: str | None = None,
    db: Session = Depends(get_db),
) -> TeaserListResponse:
    """Generated teasers for a video, best-first (FR-015).

    Defaults to the latest completed run; pass `job_id` to select a specific one.
    """
    teasers = generation_service.list_teasers(db, video_id, job_id)
    return TeaserListResponse.from_models(
        teasers, feedback_service.verdicts_for(db, [t.id for t in teasers])
    )
