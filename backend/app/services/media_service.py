"""Media business rules.

Owns the policy the media wrappers must not know about: how long a source may
be, how long a teaser may be, and where teaser files live.
"""

import logging
from pathlib import Path

from app.config import Settings
from app.errors import AppError, InvalidVideoError
from app.media import (
    CROP,
    ClipResult,
    MediaError,
    MediaInfo,
    Silence,
    cut_clip,
    probe,
)
from app.models import Video, VideoStatus
from app.services.pipeline_report import SnapReport
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


# ----------------------------------------------------------------------
# Cutting on a pause rather than through a word
# ----------------------------------------------------------------------
def _nearest(targets: list[float], value: float, max_shift: float) -> float | None:
    """The closest target within `max_shift`, or None if none is close enough.

    Refusing to move is a real answer. A boundary with no pause near it is one
    the model placed inside continuous speech, and dragging it to the nearest
    pause several seconds away would cut more than it fixed.
    """
    if not targets or max_shift <= 0:
        return None
    closest = min(targets, key=lambda target: abs(target - value))
    return closest if abs(closest - value) <= max_shift else None


def snap_window(
    start_seconds: float,
    end_seconds: float,
    silences: list[Silence],
    settings: Settings,
    source_duration: float,
    max_clip_seconds: int | None = None,
    report: SnapReport | None = None,
) -> tuple[float, float]:
    """Move a clip's boundaries onto nearby pauses in the speech.

    The model gives timestamps to the second and cannot hear where its own
    chosen moment begins, so a clip that is right about *what* to show is
    routinely a word or two wrong about where to start. That is the difference
    between a teaser and a teaser that opens on "...ementation detail".

    The two ends snap to different things, because they mean opposite events.
    A clip should start where speech *resumes* -- the end of a silence -- and
    stop where speech *pauses* -- the start of one. Snapping both to the same
    kind of boundary would reliably clip the first or last syllable.

    Each end moves independently, and either may decline to move. A shift that
    would push the clip outside the video, or outside the configured length
    limits, is refused rather than clamped: the unsnapped window was already
    valid, and a slightly worse cut point beats a clip the next stage rejects.

    `report` records how often each end actually moved. Declining to move is a
    correct outcome for any one boundary, so what needs watching is not that a
    boundary stayed put but that they all did: snapping is a documented feature
    with tests that can still be doing nothing whatsoever on real sources, and
    that possibility is invisible without counting.
    """
    ceiling = max_clip_seconds or settings.teaser_max_seconds
    max_shift = settings.teaser_snap_max_shift_seconds
    if max_shift <= 0 or not silences:
        # Deliberately not counted as two boundaries that declined to move:
        # snapping was switched off or had no pauses to work with, and folding
        # that into the move rate would report the feature as ineffective on
        # runs where it never ran at all.
        return start_seconds, end_seconds

    # Speech resumes at the end of a silence; it pauses at the start of one.
    snapped_start = _nearest(
        [silence.end_seconds for silence in silences], start_seconds, max_shift
    )
    snapped_end = _nearest(
        [silence.start_seconds for silence in silences], end_seconds, max_shift
    )

    start = snapped_start if snapped_start is not None else start_seconds
    end = snapped_end if snapped_end is not None else end_seconds

    length = end - start
    if (
        start < 0
        or end > source_duration
        or length < settings.teaser_min_seconds
        or length > ceiling
    ):
        if report is not None:
            # Both ends kept, even if one of them had found a pause: the window
            # that ships is the unsnapped one, and crediting a move that was
            # then discarded would overstate the feature.
            report.starts_kept += 1
            report.ends_kept += 1
        logger.debug(
            "Keeping the unsnapped window %.2f-%.2fs: snapping to %.2f-%.2fs "
            "would leave a %.2fs clip outside the limits",
            start_seconds, end_seconds, start, end, length,
        )
        return start_seconds, end_seconds

    if report is not None:
        for moved, shift in (
            (snapped_start is not None, start - start_seconds),
            (snapped_end is not None, end - end_seconds),
        ):
            if moved:
                report.shifts.append(shift)
        report.starts_moved += snapped_start is not None
        report.starts_kept += snapped_start is None
        report.ends_moved += snapped_end is not None
        report.ends_kept += snapped_end is None

    if (start, end) != (start_seconds, end_seconds):
        logger.info(
            "Snapped %.2f-%.2fs to %.2f-%.2fs",
            start_seconds, end_seconds, start, end,
        )
    return round(start, 3), round(end, 3)


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
    crop_mode: str = CROP,
    subtitles: Path | None = None,
) -> tuple[str, ClipResult]:
    """Validate the window, then cut the teaser. Returns (storage_key, result).

    `aspect_ratio` falls back to the server setting when a run did not choose
    one, which keeps every existing caller behaving exactly as before.
    `crop_mode` follows from the run's source type; centre-cropping is the
    default because it is right for the talking-head sources this started with.
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
            crop_mode=crop_mode,
            subtitles=subtitles,
        )
    except MediaError as exc:
        logger.error("Teaser generation failed for video %s: %s", video.id, exc)
        raise TeaserGenerationError(f"Could not generate the teaser clip. {exc}") from exc

    return key, result
