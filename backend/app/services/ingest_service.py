"""Fetching a source video from a URL.

Upload was the only way in, which meant a two-hour conference talk had to be
downloaded to a laptop and pushed back up again. This pulls it directly.

Two things make this different from an upload, and both shape the code below.

The first is time: a long video takes minutes, far longer than a request should
hold open. So the row is created immediately in `fetching` and the bytes arrive
in a background task, exactly as generation jobs already work -- the frontend
polls the video until it leaves that state.

The second is trust. An upload is bytes the user already had; a URL is an
instruction to *this server* to make a request. That is a server-side request
forgery primitive unless it is bounded, and it is bounded in two places:
`assert_fetchable` below rejects an obviously unusable URL up front, and
net_guard confines every connection the download actually opens. The second is
the one that matters -- see that module for why checking the submitted string
is not enough on its own.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models import SourceType, Video, VideoStatus, new_id
from app.services import media_service, net_guard
from app.storage import UPLOADS, Storage, StorageLimitExceeded

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
MAX_URL_LENGTH = 2048


class InvalidSourceUrlError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_SOURCE_URL", message, 400)


# ----------------------------------------------------------------------
# URL safety
# ----------------------------------------------------------------------
def assert_fetchable(url: str) -> str:
    """Validate a user-supplied URL, or raise. Returns the normalised URL.

    This is the cheap front door: it rejects a plainly unusable URL before a
    row is written or a background task is queued, so an obviously bad request
    fails synchronously with a clear message.

    It is deliberately **not** the security boundary. A check on the submitted
    string cannot see where a redirect will lead, and a name that resolves
    publicly here is free to resolve privately a moment later. Both are handled
    at connect time by net_guard, which is what actually confines the download.
    """
    if not url or len(url) > MAX_URL_LENGTH:
        raise InvalidSourceUrlError("The URL is empty or unreasonably long.")

    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise InvalidSourceUrlError(
            f"Only http and https URLs are supported, not '{parsed.scheme or 'none'}'."
        )
    if not parsed.hostname:
        raise InvalidSourceUrlError("The URL has no host.")

    try:
        net_guard.resolve_public_addresses(parsed.hostname)
    except net_guard.BlockedAddressError as exc:
        raise InvalidSourceUrlError(
            exc.message if "private or reserved" in exc.message
            else f"Could not resolve '{parsed.hostname}'. Check the URL."
        ) from None

    return url.strip()


# ----------------------------------------------------------------------
# Row lifecycle
# ----------------------------------------------------------------------
def provisional_label(url: str) -> str:
    """A readable name for a video whose real title is not known yet.

    Needed because a fetch can fail before the source ever reports a title, and
    a row left holding a placeholder like "Fetching…" reads as stuck rather than
    failed once the status has moved on.

    Derived from the URL but only ever displayed: the storage key is built from
    the generated id, so nothing here can influence where bytes are written.
    """
    parsed = urlparse(url)
    tail = PurePosixPath(parsed.path).name
    if tail and "." in tail:
        return tail[:120]
    return (parsed.hostname or "Video")[:120]


def create_video_from_url(db: Session, url: str, user_id: str) -> Video:
    """Record a video that is about to be fetched, and return it immediately.

    The row exists before a single byte is downloaded so the caller has
    something to poll. It carries no media facts yet -- those are only true once
    the file is on disk and probed.
    """
    safe_url = assert_fetchable(url)

    video = Video(
        id=new_id(),
        user_id=user_id,
        original_filename=provisional_label(safe_url),
        storage_key="",
        extension="",
        size_bytes=0,
        status=VideoStatus.FETCHING,
        source_type=SourceType.URL,
        source_url=safe_url,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    logger.info("Queued fetch for video %s", video.id)
    return video


def _mark_failed(db: Session, video: Video, message: str) -> None:
    video.status = VideoStatus.FAILED
    video.error_message = message
    db.commit()
    logger.warning("Fetch failed for video %s: %s", video.id, message)


def fetch_into_video(
    db: Session,
    storage: Storage,
    settings: Settings,
    video: Video,
) -> Video:
    """Download the video's source URL into storage and probe it.

    Never raises: like a generation job, a failure is recorded on the row so the
    frontend can report it rather than polling a status that never changes.
    """
    if not video.source_url:
        _mark_failed(db, video, "This video has no source URL to fetch.")
        return video

    # Imported here rather than at module scope: yt-dlp is a heavy import, and
    # a deployment that never fetches by URL should not pay for it at startup.
    from app.services import downloader

    try:
        assert_fetchable(video.source_url)
        result = downloader.download(
            video.source_url,
            destination_dir=storage.root(UPLOADS),
            key_stem=video.id,
            max_bytes=settings.max_upload_bytes,
            max_duration_seconds=settings.max_source_duration_seconds,
            allowed_extensions=settings.allowed_extensions,
            ffmpeg_path=settings.ffmpeg_path,
        )
    except StorageLimitExceeded:
        _mark_failed(
            db, video,
            f"The video is larger than the {settings.max_upload_mb} MB limit.",
        )
        return video
    except AppError as exc:
        _mark_failed(db, video, exc.message)
        return video
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure fetching video %s", video.id)
        _mark_failed(db, video, f"The download failed: {exc}")
        return video

    video.storage_key = result.storage_key
    video.extension = result.extension
    video.size_bytes = result.size_bytes
    video.original_filename = result.filename
    video.source_title = result.title
    video.content_type = result.content_type

    # The same probe an upload goes through. A file that downloaded cleanly can
    # still be something ffprobe will not accept, and that must be caught here
    # rather than at generation time.
    try:
        info = media_service.inspect_source(storage, settings, video)
    except AppError as exc:
        storage.delete(UPLOADS, result.storage_key)
        _mark_failed(db, video, exc.message)
        return video
    except Exception as exc:  # noqa: BLE001
        storage.delete(UPLOADS, result.storage_key)
        logger.exception("Could not probe fetched video %s", video.id)
        _mark_failed(db, video, f"The downloaded file could not be read: {exc}")
        return video

    media_service.apply_media_info(video, info)
    db.commit()
    db.refresh(video)

    logger.info(
        "Fetched video %s (%s, %d bytes, %.2fs)",
        video.id, video.original_filename, video.size_bytes,
        video.duration_seconds or 0.0,
    )
    return video
