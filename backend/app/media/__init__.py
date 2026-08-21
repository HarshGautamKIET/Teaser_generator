"""Media package.

FFmpeg and FFprobe live here and nowhere else. This package never touches the
database, HTTP concerns, or teaser policy (ARCHITECTURE.md boundaries).
"""

from app.media.ffmpeg import (
    ClipResult,
    MediaError,
    MediaInfo,
    build_filter,
    cut_clip,
    output_resolution,
    probe,
)

__all__ = [
    "ClipResult",
    "MediaError",
    "MediaInfo",
    "build_filter",
    "cut_clip",
    "output_resolution",
    "probe",
]
