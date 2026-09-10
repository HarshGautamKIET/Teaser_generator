"""Media package.

FFmpeg and FFprobe live here and nowhere else. This package never touches the
database, HTTP concerns, or teaser policy (ARCHITECTURE.md boundaries).
"""

from app.media.ffmpeg import (
    CROP,
    FIT,
    ClipResult,
    MediaError,
    MediaInfo,
    Segment,
    Silence,
    assemble,
    build_filter,
    cut_clip,
    detect_silence,
    extract_audio,
    mean_volume_db,
    output_resolution,
    probe,
)

__all__ = [
    "CROP",
    "FIT",
    "ClipResult",
    "MediaError",
    "MediaInfo",
    "Segment",
    "Silence",
    "assemble",
    "build_filter",
    "cut_clip",
    "detect_silence",
    "extract_audio",
    "mean_volume_db",
    "output_resolution",
    "probe",
]
