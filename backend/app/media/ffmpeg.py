"""FFprobe and FFmpeg wrappers.

Thin, policy-free process wrappers: they know how to read media facts and cut a
clip, and nothing about teaser rules, jobs, or storage layout. Duration and
length policy lives in services/media_service.py (ARCHITECTURE.md boundaries).

Binaries are always invoked with an argument list and never through a shell, so
no value here can be interpreted as a command (SECURITY.md).
"""

import json
import logging
import re
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

# How a frame is reconciled with an output shape that is not its own. Plain
# strings rather than the domain enum, for the same reason aspect ratios arrive
# here as "9:16": this module parses media arguments, it does not import policy.
# domain.CropMode carries the matching values for the API to validate against.
CROP = "crop"
FIT = "fit"

# silencedetect reports both ends of every silence on stderr, one per line:
#   [silencedetect @ 0x..] silence_start: 12.345
#   [silencedetect @ 0x..] silence_end: 13.567 | silence_duration: 1.222
_SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")

# volumedetect writes its summary to stderr when the stream ends:
#   [Parsed_volumedetect_0 @ 0x...] mean_volume: -23.4 dB
#   [Parsed_volumedetect_0 @ 0x...] max_volume: -3.1 dB
# A window of pure digital silence reports `-inf`, which is a real answer and
# not a parse failure, so the pattern accepts it.
_MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?[\d.]+|-inf)\s*dB")


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


def build_filter(aspect_ratio: str, crop_mode: str = "crop") -> str:
    """Fit the source to the target ratio, then scale to the target resolution.

    Two ways to reconcile a frame with a shape that is not its own:

    `crop` centre-crops, filling the frame without letterboxing or distortion,
    which is what a vertical social teaser of a person talking needs
    (VIDEO_PIPELINE.md).

    `fit` scales the whole frame down and pads what is left over. It exists for
    screen recordings, where cropping is not a trade-off but a defect: taking
    16:9 to 9:16 keeps under a third of the width, and a demo's value is the UI
    text and the result on screen, both of which are usually the first things
    outside a centre crop. Padding keeps the frame legible at the cost of bars.
    """
    width_token, height_token, _, _ = _parse_ratio(aspect_ratio)
    width, height = output_resolution(aspect_ratio)

    if crop_mode == FIT:
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease"
            f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
        )
    if crop_mode != CROP:
        raise MediaError(
            f"Unknown crop mode {crop_mode!r}. Expected {CROP!r} or {FIT!r}."
        )

    return (
        f"crop=w='min(iw,ih*{width_token}/{height_token})'"
        f":h='min(ih,iw*{height_token}/{width_token})'"
        ":x='(iw-ow)/2':y='(ih-oh)/2'"
        f",scale={width}:{height},setsar=1"
    )


# ----------------------------------------------------------------------
# Running the binaries
# ----------------------------------------------------------------------
def _run(
    command: list[str], timeout: int, tool: str, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout,
            cwd=None if cwd is None else str(cwd),
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


@dataclass(frozen=True)
class Silence:
    """One stretch of the audio track quiet enough to cut on."""

    start_seconds: float
    end_seconds: float


def detect_silence(
    source: Path,
    duration_seconds: float,
    ffmpeg_path: str = "ffmpeg",
    noise_db: int = -30,
    min_silence_seconds: float = 0.3,
) -> list[Silence]:
    """Find every silent stretch in the audio track.

    This is what stands in for a transcript. Locating the pauses is enough to
    place a cut between two words rather than through one, and it needs nothing
    that is not already installed -- FFmpeg is a hard dependency of this
    project, and an ASR model would be a new one.

    Decoding is audio-only (`-vn`) because the video stream has nothing to say
    about where the speech stops, and skipping it is most of the runtime on a
    long recording.

    Returns an empty list rather than raising when detection fails or the file
    has no audio: snapping is an improvement to a cut point, not a precondition
    for having one, and a run must not fail because the pauses could not be
    found (SECURITY.md's discipline, applied to a non-security case).
    """
    source = Path(source)
    try:
        process = _run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-vn",
                "-i", str(source),
                "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_seconds}",
                "-f", "null",
                "-",
            ],
            CUT_TIMEOUT_SECONDS,
            "FFmpeg",
        )
    except MediaError:
        # A missing binary or a wedged process. Both are worth knowing about and
        # neither is this function's to report: whatever is wrong with FFmpeg
        # will be wrong again at the cutting stage, which fails the run with an
        # error code that says so.
        logger.warning(
            "Could not run silence detection on %s", source.name, exc_info=True
        )
        return []

    if process.returncode != 0:
        logger.warning(
            "Silence detection failed for %s: %s",
            source.name, _stderr_tail(process),
        )
        return []

    starts = [float(m) for m in _SILENCE_START.findall(process.stderr or "")]
    ends = [float(m) for m in _SILENCE_END.findall(process.stderr or "")]

    # A recording that fades out at the end produces a final silence_start with
    # no silence_end -- the stream stops before the quiet does. Closing it at
    # the duration keeps that last pause usable instead of discarding it.
    if len(starts) == len(ends) + 1:
        ends.append(duration_seconds)
    elif len(starts) != len(ends):
        logger.warning(
            "Unbalanced silencedetect output for %s (%d starts, %d ends); "
            "ignoring it rather than guessing which pairs are real",
            source.name, len(starts), len(ends),
        )
        return []

    silences = [
        Silence(start_seconds=max(0.0, start), end_seconds=min(end, duration_seconds))
        for start, end in zip(starts, ends)
        if end > start
    ]
    logger.info("Found %d silence(s) in %s", len(silences), source.name)
    return silences


def mean_volume_db(
    source: Path,
    start_seconds: float,
    end_seconds: float,
    ffmpeg_path: str = "ffmpeg",
) -> float | None:
    """Average loudness of one window, in dBFS. None when it cannot be measured.

    This is what makes cut quality measurable without a human and without a
    model. A clip that opens mid-word opens at roughly the speech level of the
    rest of the clip; a clip that opens on a pause opens well below it. So the
    quality of a cut point is the *difference* between the first fraction of a
    second and the clip as a whole, and both terms are this function.

    `volumedetect` rather than `astats` or `ebur128`: it needs no filter chain,
    reports one number, and is present in every FFmpeg build. Loudness
    normalisation standards measure perceived loudness over long windows, which
    is the wrong instrument for a 150 ms question.

    Returns None rather than raising, for the same reason `detect_silence` does:
    this measures a clip that has already been cut successfully, so nothing here
    is allowed to turn a finished teaser into a failed run.
    """
    source = Path(source)
    if end_seconds <= start_seconds:
        return None

    try:
        process = _run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-nostats",
                "-ss", f"{start_seconds:.3f}",
                "-t", f"{end_seconds - start_seconds:.3f}",
                "-i", str(source),
                "-vn",
                "-af", "volumedetect",
                "-f", "null",
                "-",
            ],
            PROBE_TIMEOUT_SECONDS,
            "FFmpeg",
        )
    except MediaError:
        logger.debug("Could not measure loudness of %s", source.name, exc_info=True)
        return None

    if process.returncode != 0:
        return None

    match = _MEAN_VOLUME.search(process.stderr or "")
    if match is None:
        return None
    raw = match.group(1)
    # Digital silence. Reported as a real, very quiet measurement rather than as
    # "unmeasurable": a window with nothing in it is the cleanest possible place
    # to start a clip, and returning None would drop that from the average.
    return -120.0 if raw == "-inf" else float(raw)


@dataclass(frozen=True)
class Segment:
    """One piece of an assembled timeline.

    A `source` of None is a generated card -- black picture and silence for
    `duration_seconds` -- which is how the title and closing frames are made
    without needing an image on disk.
    """

    duration_seconds: float
    source: Path | None = None
    start_seconds: float = 0.0


def assemble(
    segments: list[Segment],
    output: Path,
    width: int,
    height: int,
    overlay: Path | None = None,
    fps: int = 30,
    source_has_audio: bool = True,
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str = "ffprobe",
) -> ClipResult:
    """Join segments into one file in a single pass.

    Everything is normalised before the join, because concat refuses streams
    that disagree: each piece is scaled and padded to the same frame, forced to
    the same frame rate, and resampled to the same audio format. A card
    contributes silence so that the audio track is continuous rather than
    stopping and restarting, which some players handle by ending playback.

    One filter graph and one encode, rather than rendering each piece to its
    own file and concatenating those. The intermediate files would each be
    encoded and immediately decoded again, which costs quality as well as time.

    `overlay` is an ASS script timed against the *assembled* timeline, so cards
    and titles are drawn after the join rather than baked into the pieces.
    """
    output = Path(output)
    if not segments:
        raise MediaError("An assembled preview needs at least one segment.")

    output.parent.mkdir(parents=True, exist_ok=True)

    inputs: list[str] = []
    video_labels: list[str] = []
    audio_labels: list[str] = []
    chains: list[str] = []
    index = 0

    for position, segment in enumerate(segments):
        if segment.duration_seconds <= 0:
            raise MediaError(
                f"Segment {position} has a non-positive duration "
                f"({segment.duration_seconds})."
            )

        real = segment.source is not None and source_has_audio
        if segment.source is not None:
            inputs += [
                "-ss", f"{segment.start_seconds:.3f}",
                "-t", f"{segment.duration_seconds:.3f}",
                "-i", str(Path(segment.source).resolve()),
            ]
        else:
            inputs += [
                "-f", "lavfi",
                "-t", f"{segment.duration_seconds:.3f}",
                "-i", f"color=c=black:s={width}x{height}:r={fps}",
            ]
        video_index = index
        index += 1

        if real:
            audio_index = video_index
        else:
            inputs += [
                "-f", "lavfi",
                "-t", f"{segment.duration_seconds:.3f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            ]
            audio_index = index
            index += 1

        chains.append(
            f"[{video_index}:v]scale={width}:{height}"
            ":force_original_aspect_ratio=decrease"
            f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
            f",setsar=1,fps={fps}[v{position}]"
        )
        chains.append(
            f"[{audio_index}:a]aresample=44100"
            ",aformat=sample_fmts=fltp:channel_layouts=stereo"
            f"[a{position}]"
        )
        video_labels.append(f"[v{position}]")
        audio_labels.append(f"[a{position}]")

    pairs = "".join(v + a for v, a in zip(video_labels, audio_labels))
    chains.append(f"{pairs}concat=n={len(segments)}:v=1:a=1[vcat][aout]")

    workdir = None
    if overlay is not None:
        overlay = Path(overlay)
        if not overlay.is_file():
            raise MediaError(f"The overlay script is missing: {overlay}")
        # Same bare-filename-with-a-working-directory trick as cut_clip: the
        # filter parses this argument, and a Windows path would arrive full of
        # characters that mean something to that parser.
        workdir = overlay.parent
        chains.append(f"[vcat]ass={overlay.name}[vout]")
        video_out = "[vout]"
    else:
        video_out = "[vcat]"

    process = _run(
        [ffmpeg_path, "-y", "-hide_banner", *inputs,
         "-filter_complex", ";".join(chains),
         "-map", video_out, "-map", "[aout]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart",
         str(output.resolve())],
        CUT_TIMEOUT_SECONDS,
        "FFmpeg",
        cwd=workdir,
    )
    if process.returncode != 0:
        output.unlink(missing_ok=True)
        raise MediaError(f"FFmpeg could not assemble the preview: {_stderr_tail(process)}")
    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise MediaError("FFmpeg reported success but produced no preview.")

    logger.info("Assembled a %d-segment preview -> %s", len(segments), output.name)
    return ClipResult(
        path=output,
        size_bytes=output.stat().st_size,
        info=probe(output, ffprobe_path),
    )


def extract_audio(
    source: Path,
    output: Path,
    start_seconds: float,
    end_seconds: float,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """Write one window's audio to a mono 16kHz WAV.

    Speech recognition gains nothing from stereo or from a 48kHz sample rate,
    and this file is about to be sent over the wire: mono 16kHz is the usual
    input format for the task and roughly a twelfth the size of the source
    audio. A minute of it is a few hundred kilobytes.
    """
    source, output = Path(source), Path(output)
    if end_seconds <= start_seconds:
        raise MediaError(
            f"End time ({end_seconds}s) must be after start time ({start_seconds}s)."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    process = _run(
        [
            ffmpeg_path, "-y",
            "-ss", f"{start_seconds:.3f}",
            "-i", str(source),
            "-t", f"{end_seconds - start_seconds:.3f}",
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            str(output),
        ],
        CUT_TIMEOUT_SECONDS,
        "FFmpeg",
    )
    if process.returncode != 0:
        output.unlink(missing_ok=True)
        raise MediaError(f"FFmpeg could not extract the audio: {_stderr_tail(process)}")
    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise MediaError("FFmpeg reported success but produced no audio.")
    return output


def cut_clip(
    source: Path,
    output: Path,
    start_seconds: float,
    end_seconds: float,
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str = "ffprobe",
    aspect_ratio: str = "9:16",
    crop_mode: str = CROP,
    subtitles: Path | None = None,
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

    video_filter = build_filter(aspect_ratio, crop_mode)
    workdir = None
    if subtitles is not None:
        subtitles = Path(subtitles)
        if not subtitles.is_file():
            raise MediaError(f"The subtitle file is missing: {subtitles}")
        # Burned last, so the text is rendered at the output resolution rather
        # than scaled up with the picture.
        #
        # Referenced by bare filename with the process started in its own
        # directory. The filter parses its argument, so a Windows path would
        # arrive carrying a drive-letter colon and backslashes -- all of which
        # mean something to that parser and need escaping that differs per
        # platform. Not passing a path at all is the one approach with nothing
        # to escape.
        #
        # No styling is supplied here: the ASS script carries its own, stated
        # against its own declared resolution, which is the only way those
        # numbers mean pixels (services/caption_service.py).
        workdir = subtitles.parent
        video_filter = f"{video_filter},ass={subtitles.name}"

    process = _run(
        [
            ffmpeg_path, "-y",
            "-ss", f"{start_seconds:.3f}",
            "-i", str(source),
            "-t", f"{duration:.3f}",
            "-vf", video_filter,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output.resolve()),
        ],
        CUT_TIMEOUT_SECONDS,
        "FFmpeg",
        cwd=workdir,
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
