"""yt-dlp, wrapped so the rest of the app never sees it.

Everything yt-dlp-shaped is confined here: option construction, its exception
types, and the fact that it writes files itself rather than handing back a
stream. Callers get a `DownloadResult` or an `AppError`.

The options below are deliberately restrictive. yt-dlp is a large surface aimed
at interactive use, and several of its defaults are wrong for a server that is
handed URLs by strangers -- it will happily follow a playlist to a thousand
videos, run an arbitrary post-processor, or read a user's cookie jar. Each is
turned off explicitly rather than trusted to stay off.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePath

from app.errors import AppError, InvalidVideoError
from app.services.net_guard import guarded_connections
from app.storage import StorageLimitExceeded

logger = logging.getLogger(__name__)


def safe_filename(name: str, extension: str) -> str:
    """A display filename built from a source-supplied title.

    The title comes from a third-party site, so it is treated as hostile: only
    the basename survives, path separators cannot, and the result is length
    capped. Display only -- it is never used as a storage key.
    """
    stem = PurePath(name.replace("\\", "/")).name.strip() or "video"
    cleaned = "".join(
        character for character in stem
        if character.isalnum() or character in " ._-()[]"
    ).strip()
    return f"{(cleaned or 'video')[:120]}{extension}"


class DownloadError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("SOURCE_FETCH_FAILED", message, 502)


@dataclass(frozen=True)
class DownloadResult:
    storage_key: str
    extension: str
    size_bytes: int
    filename: str
    title: str | None
    content_type: str | None


def _format_selector() -> str:
    """Progressive if the site offers one, merged video+audio otherwise.

    The merged branch is not an optimisation to be avoided -- it is the only
    branch that works on YouTube. YouTube serves separate video-only and
    audio-only streams for essentially everything now, so a selector that
    accepts only muxed formats (`best`, which means "best format containing
    both") matches nothing and fails with "Requested format is not available".

    Progressive still leads because a direct MP4 link is exactly that, and
    taking it avoids a needless second request and remux.

    Height is capped so a two-hour 4K talk cannot blow the size limit before
    the duration check has had a chance to reject it. Nothing here filters on
    `filesize`: DASH manifests often omit it, and a predicate on a missing
    field excludes the format rather than ignoring the condition -- which is
    how the first version of this managed to rule out every option.
    """
    return (
        "best[ext=mp4][height<=1080]"
        "/best[height<=1080]"
        "/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
        "/bestvideo[height<=1080]+bestaudio"
        "/best"
    )


def _resolve_ffmpeg(configured: str) -> str | None:
    """An absolute path to ffmpeg, or None to let yt-dlp look for itself.

    `ffmpeg_location` is a filesystem path to yt-dlp, not a command to run, so
    handing it the app's default of `"ffmpeg"` makes it search for a file of
    that literal name relative to the working directory. It does not fall back
    to PATH after that -- it reports ffmpeg as not installed and refuses to
    merge, which is exactly what happened here: the binary was on PATH the
    whole time at /usr/bin/ffmpeg.
    """
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    # An explicit path that exists is trusted as given; anything else is left
    # to yt-dlp, whose own discovery is better than a wrong answer.
    return configured if Path(configured).is_file() else None


def download(
    url: str,
    destination_dir: Path,
    key_stem: str,
    max_bytes: int,
    max_duration_seconds: int,
    allowed_extensions: set[str],
    ffmpeg_path: str = "ffmpeg",
) -> DownloadResult:
    """Fetch `url` into `destination_dir` as `key_stem.<ext>`.

    The filename is built from the caller's generated id, never from the URL or
    the remote title, so a hostile source cannot choose where bytes land.
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - configuration failure
        raise DownloadError(
            "URL fetching is not available: yt-dlp is not installed."
        ) from exc

    destination_dir.mkdir(parents=True, exist_ok=True)

    options = {
        "format": _format_selector(),
        # %(ext)s is filled by yt-dlp; the stem is ours.
        "outtmpl": str(destination_dir / f"{key_stem}.%(ext)s"),
        # Separate streams are muxed into one MP4.
        "merge_output_format": "mp4",
        "max_filesize": max_bytes,
        "noplaylist": True,          # a playlist URL fetches one video, not all of it
        "playlist_items": "1",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 2,
        "socket_timeout": 30,
        # Fragments must download on this thread. The address guard below is
        # thread-local, so work handed to a worker pool would slip past it.
        "concurrent_fragment_downloads": 1,
        "nocheckcertificate": False,  # never weaken TLS for a remote fetch
        "cookiesfrombrowser": None,   # never read a local browser's cookies
        "postprocessors": [],
        # Only ever speak HTTP(S). Without this a file:// or ftp:// extractor
        # could be reached through a redirect and read the container's disk.
        "allowed_extractors": ["default"],
    }

    # Only set when it resolves to something real; a bad value is worse than
    # none, because it stops yt-dlp finding the binary on PATH by itself.
    located = _resolve_ffmpeg(ffmpeg_path)
    if located:
        options["ffmpeg_location"] = located

    # Every connection yt-dlp opens from here on -- including ones it is sent to
    # by a redirect, which the URL check before this could not see -- must land
    # on a public address.
    guard = None
    try:
        with guarded_connections() as guard, yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                raise DownloadError("Nothing could be extracted from that URL.")
            if info.get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if e]
                if not entries:
                    raise DownloadError("That URL is an empty playlist.")
                info = entries[0]

            # Checked before downloading: refusing a three-hour stream after
            # pulling two gigabytes would be a waste of everyone's bandwidth.
            duration = info.get("duration")
            if duration and duration > max_duration_seconds:
                raise InvalidVideoError(
                    f"The video is {duration / 60:.0f} minutes long, which exceeds "
                    f"the {max_duration_seconds / 60:.0f} minute limit."
                )

            if info.get("is_live"):
                raise InvalidVideoError("Live streams cannot be used as a source.")

            declared = info.get("filesize") or info.get("filesize_approx")
            if declared and declared > max_bytes:
                raise StorageLimitExceeded(
                    f"Source reports {declared} bytes, over the {max_bytes} limit."
                )

            downloaded = ydl.extract_info(url, download=True)
            if downloaded is None:
                raise DownloadError("The download produced nothing.")
            if downloaded.get("_type") == "playlist":
                downloaded = [e for e in (downloaded.get("entries") or []) if e][0]

    except (AppError, StorageLimitExceeded):
        raise
    except Exception as exc:  # noqa: BLE001
        # A refused address surfaces here wrapped in yt-dlp's own error type, so
        # the guard's reason is recovered rather than reported as a generic
        # download failure -- "that URL points somewhere private" is actionable
        # in a way that "it may be region-locked" is not.
        if guard is not None and guard.blocked:
            logger.warning(
                "Refused a source URL on address grounds: %s", guard.reason
            )
            raise DownloadError(guard.reason) from exc

        # yt-dlp raises a family of its own errors, and their messages can carry
        # the full request URL and internal detail. Log it, return something
        # short enough to show a user.
        logger.warning("yt-dlp failed for a source URL: %s", exc)
        raise DownloadError(
            "The video could not be downloaded from that URL. It may be private, "
            "region-locked, or not a video page."
        ) from exc

    produced = _locate_output(destination_dir, key_stem)
    if produced is None:
        raise DownloadError("The download finished but produced no file.")

    extension = produced.suffix.lower()
    if extension not in allowed_extensions:
        produced.unlink(missing_ok=True)
        raise InvalidVideoError(
            f"The source produced a '{extension}' file, which is not a supported "
            f"format ({', '.join(sorted(allowed_extensions))})."
        )

    size_bytes = produced.stat().st_size
    if size_bytes == 0:
        produced.unlink(missing_ok=True)
        raise InvalidVideoError("The downloaded file is empty.")
    if size_bytes > max_bytes:
        # max_filesize is advisory for some extractors, so the real size is
        # checked once the bytes have actually landed.
        produced.unlink(missing_ok=True)
        raise StorageLimitExceeded(f"Downloaded {size_bytes} bytes, over the limit.")

    title = downloaded.get("title") or None
    return DownloadResult(
        storage_key=produced.name,
        extension=extension,
        size_bytes=size_bytes,
        filename=safe_filename(title or "video", extension),
        title=title,
        content_type=f"video/{extension.lstrip('.')}",
    )


def _locate_output(destination_dir: Path, key_stem: str) -> Path | None:
    """Find what the download actually wrote.

    The extension is chosen by yt-dlp from the format it settled on, so the
    result is discovered rather than assumed.

    A merged download writes per-stream files first -- `<stem>.f137.mp4`,
    `<stem>.f140.m4a` -- and muxes them into `<stem>.mp4`. yt-dlp removes the
    parts itself, but an interrupted run can leave them, and they match the
    same glob. The merged file is the one whose stem is exactly ours, so that
    is preferred outright rather than guessed at by size.
    """
    candidates = [
        path for path in destination_dir.glob(f"{key_stem}.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        return None

    exact = [path for path in candidates if path.stem == key_stem]
    chosen = (
        max(exact, key=lambda path: path.stat().st_size)
        if exact
        else max(candidates, key=lambda path: path.stat().st_size)
    )

    # Anything else sharing the stem is debris from this download.
    for leftover in candidates:
        if leftover != chosen:
            leftover.unlink(missing_ok=True)
    return chosen
