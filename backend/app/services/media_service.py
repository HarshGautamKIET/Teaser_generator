"""Media business rules.

Owns the policy the media wrappers must not know about: how long a source may
be, how long a teaser may be, and where teaser files live.
"""

import logging
from pathlib import Path

from app.config import Settings
from app.errors import AppError, InvalidVideoError
from app.media import ClipResult, MediaError, MediaInfo, cut_clip, probe
from app.models import Video, VideoStatus
from app.storage import GENERATED, UPLOADS, Storage

logger = logging.getLogger(__name__)


class TeaserGenerationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("TEASER_GENERATION_FAILED", message, 500)


# ----------------------------------------------------------------------
# Source video inspection (FR-002)
# ----------------------------------------------------------------------
def inspect_source(storage: Storage, settings: Settings, video: Video) -> MediaInfo:
    """Probe an uploaded video and enforce source-duration limits."""
    path = storage.resolve(UPLOADS, video.storage_key)
    try:
        info = probe(path, settings.ffprobe_path)
    except MediaError as exc:
        raise InvalidVideoError(f"The uploaded file is not a readable video. {exc}") from exc

    if info.duration_seconds > settings.max_source_duration_seconds:
        limit_minutes = settings.max_source_duration_seconds / 60
        raise InvalidVideoError(
            f"The video is {info.duration_seconds / 60:.1f} minutes long, "
            f"which exceeds the {limit_minutes:.0f} minute limit."
        )

    if info.duration_seconds < settings.teaser_min_seconds:
        raise InvalidVideoError(
            f"The video is only {info.duration_seconds:.1f}s long -- shorter than "
            f"the {settings.teaser_min_seconds}s minimum teaser length."
        )
    return info


def apply_media_info(video: Video, info: MediaInfo) -> Video:
    """Copy probed facts onto the video record."""
    video.duration_seconds = info.duration_seconds
    video.width = info.width
    video.height = info.height
    video.fps = info.fps
    video.status = VideoStatus.READY
    return video


# ----------------------------------------------------------------------
# Teaser length policy (VIDEO_PIPELINE.md)
# ----------------------------------------------------------------------
def validate_clip_window(
    settings: Settings,
    start_seconds: float,
    end_seconds: float,
    source_duration: float,
) -> None:
    """Reject a clip window that breaks the configured teaser rules.

    Applied to every AI-proposed timestamp before FFmpeg runs (FR-009).
    """
    if start_seconds < 0:
        raise TeaserGenerationError(f"Start time cannot be negative: {start_seconds}.")
    if end_seconds <= start_seconds:
        raise TeaserGenerationError(
            f"End time ({end_seconds}s) must be after start time ({start_seconds}s)."
        )
    if end_seconds > source_duration:
        raise TeaserGenerationError(
            f"End time ({end_seconds}s) exceeds the video duration "
            f"({source_duration:.2f}s)."
        )

    length = end_seconds - start_seconds
    if length < settings.teaser_min_seconds:
        raise TeaserGenerationError(
            f"Clip is {length:.2f}s, shorter than the "
            f"{settings.teaser_min_seconds}s minimum."
        )
    if length > settings.teaser_max_seconds:
        raise TeaserGenerationError(
            f"Clip is {length:.2f}s, longer than the "
            f"{settings.teaser_max_seconds}s maximum."
        )


def teaser_storage_key(video_id: str, teaser_id: str) -> str:
    """generated/<video_id>/teaser_<teaser_id>.mp4 (VIDEO_PIPELINE.md)."""
    return f"{video_id}/teaser_{teaser_id}.mp4"


def generate_teaser(
    storage: Storage,
    settings: Settings,
    video: Video,
    teaser_id: str,
    start_seconds: float,
    end_seconds: float,
    aspect_ratio: str | None = None,
) -> tuple[str, ClipResult]:
    """Validate the window, then cut the teaser. Returns (storage_key, result).

    `aspect_ratio` falls back to the server setting when a run did not choose
    one, which keeps every existing caller behaving exactly as before.
    """
    validate_clip_window(
        settings, start_seconds, end_seconds, video.duration_seconds or 0.0
    )

    key = teaser_storage_key(video.id, teaser_id)
    source: Path = storage.resolve(UPLOADS, video.storage_key)
    output: Path = storage.resolve(GENERATED, key)

    try:
        result = cut_clip(
            source=source,
            output=output,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            ffmpeg_path=settings.ffmpeg_path,
            ffprobe_path=settings.ffprobe_path,
            aspect_ratio=aspect_ratio or settings.teaser_aspect_ratio,
        )
    except MediaError as exc:
        logger.error("Teaser generation failed for video %s: %s", video.id, exc)
        raise TeaserGenerationError(f"Could not generate the teaser clip. {exc}") from exc

    return key, result
