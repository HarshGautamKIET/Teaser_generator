"""Video upload and lookup logic.

Routes stay thin; this module owns validation and persistence rules.
"""

import logging
from pathlib import PurePath
from typing import NamedTuple

from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import InvalidVideoError, NotFoundError, VideoTooLargeError
from app.models import Job, Teaser, Video, VideoStatus, new_id
from app.services import media_service
from app.storage import UPLOADS, Storage, StorageLimitExceeded

logger = logging.getLogger(__name__)


def _validate_extension(filename: str | None, settings: Settings) -> str:
    """Return the lowercased extension, or raise if unsupported (FR-002)."""
    if not filename:
        raise InvalidVideoError("No filename was provided with the upload.")

    # Take the suffix only -- the client-supplied name is never trusted as a path.
    extension = PurePath(filename).suffix.lower()
    if not extension:
        raise InvalidVideoError("The uploaded file has no extension.")

    allowed = settings.allowed_extensions
    if extension not in allowed:
        supported = ", ".join(sorted(allowed))
        raise InvalidVideoError(
            f"Unsupported video format '{extension}'. Supported formats: {supported}."
        )
    return extension


def create_video_from_upload(
    db: Session,
    storage: Storage,
    settings: Settings,
    upload: UploadFile,
    user_id: str,
) -> Video:
    """Validate, store, and record an uploaded source video (FR-001..FR-003)."""
    extension = _validate_extension(upload.filename, settings)

    # Storage key is derived from a generated id, never from user input.
    video_id = new_id()
    storage_key = f"{video_id}{extension}"

    try:
        size_bytes = storage.save_stream(
            UPLOADS, storage_key, upload.file, settings.max_upload_bytes
        )
    except StorageLimitExceeded:
        raise VideoTooLargeError(
            f"The video exceeds the maximum upload size of {settings.max_upload_mb} MB."
        ) from None

    if size_bytes == 0:
        storage.delete(UPLOADS, storage_key)
        raise InvalidVideoError("The uploaded file is empty.")

    video = Video(
        id=video_id,
        user_id=user_id,
        original_filename=PurePath(upload.filename or "").name,
        storage_key=storage_key,
        extension=extension,
        size_bytes=size_bytes,
        content_type=upload.content_type,
        status=VideoStatus.UPLOADED,
    )

    # Confirm this is real, usable video before it is recorded (FR-002).
    try:
        info = media_service.inspect_source(storage, settings, video)
    except Exception:
        storage.delete(UPLOADS, storage_key)
        raise
    media_service.apply_media_info(video, info)

    db.add(video)
    db.commit()
    db.refresh(video)

    logger.info(
        "Uploaded video %s (%s, %d bytes, %.2fs, %dx%d)",
        video.id, video.original_filename, size_bytes,
        video.duration_seconds or 0.0, video.width or 0, video.height or 0,
    )
    return video


def get_video(db: Session, video_id: str) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise NotFoundError("VIDEO_NOT_FOUND", f"No video found with id {video_id}.")
    return video


class VideoWithCounts(NamedTuple):
    video: Video
    job_count: int
    teaser_count: int


def list_videos(db: Session) -> list[VideoWithCounts]:
    """Every source video the caller owns, newest first.

    No user filter appears here because none is needed: the session runs as the
    caller under RLS, so this query can only ever see their own rows.

    Counts come from two grouped queries rather than a subquery per row, so the
    listing costs three round trips whatever the library size.
    """
    jobs = dict(
        db.query(Job.video_id, func.count(Job.id)).group_by(Job.video_id).all()
    )
    teasers = dict(
        db.query(Teaser.video_id, func.count(Teaser.id))
        .group_by(Teaser.video_id)
        .all()
    )
    return [
        VideoWithCounts(video, jobs.get(video.id, 0), teasers.get(video.id, 0))
        for video in db.query(Video).order_by(Video.created_at.desc()).all()
    ]
