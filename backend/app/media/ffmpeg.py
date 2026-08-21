"""FFprobe and FFmpeg wrappers.

Thin, policy-free process wrappers: they know how to read media facts and cut a
clip, and nothing about teaser rules, jobs, or storage layout. Duration and
length policy lives in services/media_service.py (ARCHITECTURE.md boundaries).

Binaries are always invoked with an argument list and never through a shell, so
no value here can be interpreted as a command (SECURITY.md).
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Long enough for a full-length re-encode, short enough that a wedged process
# cannot hold a job open forever.
PROBE_TIMEOUT_SECONDS = 60
CUT_TIMEOUT_SECONDS = 600

# The shorter side of every teaser, in pixels: 1080 keeps 9:16 at 1080x1920.
BASE_PIXELS = 1080


class MediaError(Exception):
    """FFmpeg/FFprobe could not do what was asked.

    Callers in the service layer translate this into a client-facing AppError;
    it is deliberately not one itself.
    """


@dataclass(frozen=True)
class MediaInfo:
    """What FFprobe actually found in a file."""

    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: str
    has_audio: bool


@dataclass(frozen=True)
class ClipResult:
    """A clip that exists on disk, with its probed facts."""

    path: Path
    size_bytes: int
    info: MediaInfo


# ----------------------------------------------------------------------
# Output geometry -- pure functions, no binaries involved
# ----------------------------------------------------------------------
def _parse_ratio(aspect_ratio: str) -> tuple[str, str, float, float]:
    """Split "9:16" into its raw tokens and their numeric values."""
    parts = aspect_ratio.split(":")
    if len(parts) != 2:
        raise MediaError(
            f"Invalid aspect ratio {aspect_ratio!r}. Expected a form like '9:16'."
        )

    width_token, height_token = (part.strip() for part in parts)
    try:
        width_value = float(width_token)
        height_value = float(height_token)
    except ValueError:
        raise MediaError(
            f"Invalid aspect ratio {aspect_ratio!r}. Both sides must be numbers."
        ) from None

    if width_value <= 0 or height_value <= 0:
        raise MediaError(
            f"Invalid aspect ratio {aspect_ratio!r}. Both sides must be positive."
        )
    return width_token, height_token, width_value, height_value


def _even(value: float) -> int:
    """H.264 requires even dimensions."""
    pixels = int(round(value))
    return pixels if pixels % 2 == 0 else pixels + 1


def output_resolution(aspect_ratio: str) -> tuple[int, int]:
    """Target (width, height) for an aspect ratio, shorter side at 1080."""
    _, _, width_value, height_value = _parse_ratio(aspect_ratio)

    if width_value <= height_value:
        width, height = BASE_PIXELS, BASE_PIXELS * height_value / width_value
    else:
        width, height = BASE_PIXELS * width_value / height_value, BASE_PIXELS
    return _even(width), _even(height)


def build_filter(aspect_ratio: str) -> str:
    """Centre-crop to the target ratio, then scale to the target resolution.

    Cropping before scaling fills the frame without letterboxing or distortion,
    which is what a vertical social teaser needs (VIDEO_PIPELINE.md).
    """
    width_token, height_token, _, _ = _parse_ratio(aspect_ratio)
    width, height = output_resolution(aspect_ratio)

    return (
        f"crop=w='min(iw,ih*{width_token}/{height_token})'"
        f":h='min(ih,iw*{height_token}/{width_token})'"
        ":x='(iw-ow)/2':y='(ih-oh)/2'"
        f",scale={width}:{height},setsar=1"
    )


# ----------------------------------------------------------------------
# Running the binaries
# ----------------------------------------------------------------------
def _run(command: list[str], timeout: int, tool: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        raise MediaError(
            f"{tool} executable not found: {command[0]!r}. "
            "Install it or set FFMPEG_PATH/FFPROBE_PATH in .env."
        ) from None
    except subprocess.TimeoutExpired:
        raise MediaError(f"{tool} timed out after {timeout}s.") from None


def _stderr_tail(process: subprocess.CompletedProcess, lines: int = 3) -> str:
    """The last few stderr lines -- enough to diagnose, short enough to log."""
    text = (process.stderr or "").strip()
    return " ".join(text.splitlines()[-lines:]) if text else "no output"


def _parse_fps(stream: dict) -> float:
    """Turn FFprobe's "15/1" rate into a float."""
    for key in ("avg_frame_rate", "r_frame_rate"):
        rate = stream.get(key)
        if not rate or rate == "0/0":
            continue
        numerator, _, denominator = rate.partition("/")
        try:
            denominator_value = float(denominator) if denominator else 1.0
            if denominator_value:
                return float(numerator) / denominator_value
        except ValueError:
            continue
    return 0.0


def _parse_duration(payload: dict, stream: dict) -> float:
    """Container duration, falling back to the video stream's own."""
    for source in (payload.get("format", {}), stream):
        raw = source.get("duration")
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def probe(path: Path, ffprobe_path: str = "ffprobe") -> MediaInfo:
    """Read the real facts about a media file.

    Every downstream decision -- duration limits, timestamp validation, output
    geometry -- is made against this, never against what a client or the AI
    claims about the file.
    """
    path = Path(path)
    if not path.is_file():
        raise MediaError(f"The file does not exist: {path}")

    process = _run(
        [
            ffprobe_path,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        PROBE_TIMEOUT_SECONDS,
        "FFprobe",
    )
    if process.returncode != 0:
        raise MediaError(f"FFprobe could not read {path.name}: {_stderr_tail(process)}")

    try:
        payload = json.loads(process.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaError(f"FFprobe returned unreadable output for {path.name}.") from exc

    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError(f"{path.name} contains no video stream.")

    return MediaInfo(
        duration_seconds=_parse_duration(payload, video),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_parse_fps(video),
        video_codec=str(video.get("codec_name") or ""),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
    )


def cut_clip(
    source: Path,
    output: Path,
    start_seconds: float,
    end_seconds: float,
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str = "ffprobe",
    aspect_ratio: str = "9:16",
) -> ClipResult:
    """Cut [start, end) out of `source` and write a teaser to `output`.

    The window is re-checked here even though the service layer already applied
    the teaser-length policy: this module must not depend on being called
    correctly before it hands numbers to a subprocess.
    """
    source, output = Path(source), Path(output)

    if not source.is_file():
        raise MediaError(f"The source file is missing: {source}")
    if start_seconds < 0:
        raise MediaError(f"Start time cannot be negative: {start_seconds}.")
    if end_seconds <= start_seconds:
        raise MediaError(
            f"End time ({end_seconds}s) must be after start time ({start_seconds}s)."
        )

    duration = end_seconds - start_seconds
    output.parent.mkdir(parents=True, exist_ok=True)

    process = _run(
        [
            ffmpeg_path, "-y",
            "-ss", f"{start_seconds:.3f}",
            "-i", str(source),
            "-t", f"{duration:.3f}",
            "-vf", build_filter(aspect_ratio),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output),
        ],
        CUT_TIMEOUT_SECONDS,
        "FFmpeg",
    )
    if process.returncode != 0:
        output.unlink(missing_ok=True)
        raise MediaError(f"FFmpeg failed to cut the clip: {_stderr_tail(process)}")
    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise MediaError("FFmpeg reported success but produced no clip.")

    logger.info(
        "Cut %.2fs clip from %s -> %s", duration, source.name, output.name
    )
    return ClipResult(
        path=output,
        size_bytes=output.stat().st_size,
        info=probe(output, ffprobe_path),
    )
