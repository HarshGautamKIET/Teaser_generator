"""Turning transcribed lines into a subtitle file.

Transcription output is untrusted in exactly the way candidate moments are, and
for the same reason: it is whatever the model said. The difference is what it
reaches. A bad timestamp here does not become an argument to FFmpeg -- it
becomes a line in a file FFmpeg renders -- so the failure mode is a caption that
displays at the wrong moment or never displays at all, rather than a broken cut.

That still has to be prevented, because libass will happily render overlapping
cues on top of each other, and a cue running past the end of a clip is one the
viewer never sees.

ASS rather than SubRip, which is the more obvious choice. An SRT carries no
styling, so the style has to be supplied at burn time through the subtitles
filter's `force_style` -- and libass then interprets those numbers against a
virtual canvas of its own (288 lines tall), not against the video. `Fontsize=44`
came out roughly 290 pixels on a 1080x1920 clip and `MarginV=90` placed the text
across the middle of the frame. An ASS script states its own PlayResX/PlayResY,
so setting them to the real output resolution makes every number here a pixel.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.ai.base import MAX_CAPTION_CHARS, RawTranscript
from app.services.analysis_service import clean_text

logger = logging.getLogger(__name__)

# Below this a cue flashes rather than reads. Cues shorter than this are
# extended, not dropped: the words were spoken, and a caption that is hard to
# read beats one that is missing.
MIN_CUE_SECONDS = 0.4

# Style numbers, in pixels of the output frame (see the module docstring).
# 44px stays readable on a phone held at arm's length; the opaque box behind it
# (BorderStyle 3 with a semi-transparent BackColour) keeps it legible over a
# bright slide, which an outline alone does not. Alignment 2 with a 90px bottom
# margin clears the platform UI along the bottom edge of a vertical video.
FONT_SIZE = 44
MARGIN_V = 90
MARGIN_H = 60

# ASS override tags are written in braces, so a brace arriving in transcribed
# text would be read as markup rather than shown.
_BRACES = re.compile(r"[{}]")


@dataclass
class Caption:
    """One validated caption cue, timed from the start of its clip."""

    start_seconds: float
    end_seconds: float
    text: str


def ass_timestamp(seconds: float) -> str:
    """ASS wants H:MM:SS.cc -- one hour digit, centiseconds, no padding."""
    centiseconds = int(round(seconds * 100))
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    whole_seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours:d}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def escape_ass_text(value: str) -> str:
    """Make a string safe to place in an ASS dialogue line.

    Braces open and close override tags, so text containing one would be read
    as markup and disappear from the picture. Newlines become the explicit
    line break, since a dialogue line ends at the newline.
    """
    return _BRACES.sub("", value).replace("\n", "\\N")


def validate_captions(
    transcript: RawTranscript, clip_duration: float
) -> list[Caption]:
    """Clean the cues and make them displayable. Never raises.

    Cues are put in order, clamped to the clip, and pulled apart where they
    overlap -- an overlap is two lines drawn over each other, which is worse
    than either alone.
    """
    cleaned: list[Caption] = []
    for raw in transcript.captions or []:
        text = clean_text(raw.text, MAX_CAPTION_CHARS)
        if not text:
            continue

        start = max(0.0, raw.start_seconds)
        end = min(raw.end_seconds, clip_duration)
        if start >= clip_duration or end <= start:
            continue
        cleaned.append(Caption(start_seconds=start, end_seconds=end, text=text))

    cleaned.sort(key=lambda cue: cue.start_seconds)

    captions: list[Caption] = []
    for cue in cleaned:
        if captions and cue.start_seconds < captions[-1].end_seconds:
            # Truncate the one already placed rather than delaying this one,
            # so a cue never appears after the words it captions were spoken.
            captions[-1].end_seconds = cue.start_seconds
            if captions[-1].end_seconds <= captions[-1].start_seconds:
                captions.pop()

        if cue.end_seconds - cue.start_seconds < MIN_CUE_SECONDS:
            cue.end_seconds = min(cue.start_seconds + MIN_CUE_SECONDS, clip_duration)
        if cue.end_seconds > cue.start_seconds:
            captions.append(cue)

    dropped = len(transcript.captions or []) - len(captions)
    if dropped:
        logger.info("Discarded %d unusable caption cue(s)", dropped)
    return captions


def to_ass(captions: list[Caption], width: int, height: int) -> str:
    """Render cues as an ASS script sized to the output frame.

    Colours are ASS's &HAABBGGRR: blue and red are the other way round from
    HTML, and the leading pair is *transparency* rather than opacity, so
    &H00FFFFFF is opaque white and &H90000000 is a black box at about 44%.
    """
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,DejaVu Sans,{FONT_SIZE},&H00FFFFFF,&H000000FF,"
        f"&H00000000,&H90000000,-1,0,0,0,100,100,0,0,3,4,0,2,"
        f"{MARGIN_H},{MARGIN_H},{MARGIN_V},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    lines = [
        f"Dialogue: 0,{ass_timestamp(cue.start_seconds)},"
        f"{ass_timestamp(cue.end_seconds)},Default,,0,0,0,,"
        f"{escape_ass_text(cue.text)}"
        for cue in captions
    ]
    return header + "".join(f"{line}\n" for line in lines)


def write_ass(
    captions: list[Caption], path: Path, width: int, height: int
) -> Path | None:
    """Write the cues beside the clip. Returns None when there is nothing to say.

    UTF-8 without a BOM: libass reads it, and a BOM would be rendered as a
    stray glyph at the start of the first cue.
    """
    if not captions:
        return None

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_ass(captions, width, height), encoding="utf-8")
    return path
