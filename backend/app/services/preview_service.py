"""Assembling one preview spot from several moments.

The rest of the pipeline produces excerpts: a set of clips, each of which has to
stand alone. That is the right output for repurposing a talk, and the wrong one
for answering "what is this course?" -- three disconnected extracts leave the
viewer to assemble the answer themselves.

So this builds the other thing. One file, made of the opening seconds of each
selected moment, held together by text: a card at the front, the moment's own
title over each beat, and a card at the end. The text is what makes the beats a
sequence rather than a supercut -- it supplies the context each fragment is
missing, which is exactly the context the self-containment rules spend their
time insisting individual clips must not need.

Nothing here calls the model. The moments, their titles and the summary were all
produced by the analysis that already ran, so a preview costs one FFmpeg pass and
no tokens.
"""

import logging
import re
from dataclasses import dataclass

from app.media import Segment
from app.services.analysis_service import Candidate
from app.services.caption_service import ass_timestamp, escape_ass_text

logger = logging.getLogger(__name__)

# A beat is the opening of a moment, not the whole of it. After snapping, a
# moment starts on a clean speech onset, and the first few seconds of something
# chosen for having a strong hook are that hook.
BEAT_SECONDS = 5.0
OPENING_CARD_SECONDS = 2.5
CLOSING_CARD_SECONDS = 2.0
# How long a moment's title stays up once its beat begins. Long enough to read,
# short enough to leave most of the beat unobstructed.
TITLE_SECONDS = 2.5

# Beyond this the spot stops being a preview. Four beats plus cards lands around
# twenty-five seconds, which is roughly where attention goes on a feed.
MAX_BEATS = 4

CLOSING_TEXT = "Watch the full session"
FALLBACK_OPENING = "In this session"

# Cards carry short lines at a large size; a headline that overruns turns into a
# wall of text covering the frame.
MAX_CARD_CHARS = 90

FONT_SIZE_CARD = 64
FONT_SIZE_TITLE = 40
MARGIN_V_TITLE = 90
MARGIN_H = 80

_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


@dataclass(frozen=True)
class Preview:
    """A plan for one assembled spot: what to cut, and what to draw over it."""

    segments: list[Segment]
    overlay: str

    @property
    def duration_seconds(self) -> float:
        return sum(segment.duration_seconds for segment in self.segments)


def headline(summary: str | None) -> str:
    """The opening card's line, taken from the run's own summary.

    Its first sentence, because a summary is written to be read at leisure and a
    card is read in two seconds. Falls back to a neutral lead rather than an
    empty card when the run produced no summary -- which happens whenever the
    model returned moments and nothing else.
    """
    text = (summary or "").strip()
    if not text:
        return FALLBACK_OPENING

    first = _SENTENCE_END.split(text, maxsplit=1)[0].strip()
    if len(first) > MAX_CARD_CHARS:
        first = first[: MAX_CARD_CHARS - 1].rstrip() + "…"
    return first or FALLBACK_OPENING


def _styles(width: int, height: int) -> str:
    """Two styles: a centred card headline and a lower-third title.

    Sizes are in pixels because PlayResX/PlayResY below are the real output
    frame -- see caption_service for what happens when they are not.
    """
    return (
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
        # Alignment 5 is centred both ways, for text over a black card.
        f"Style: Card,DejaVu Sans,{FONT_SIZE_CARD},&H00FFFFFF,&H000000FF,"
        f"&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,"
        f"{MARGIN_H},{MARGIN_H},0,1\n"
        # Alignment 2 is bottom-centred, over picture, so it needs the box
        # behind it that the card does not.
        f"Style: Title,DejaVu Sans,{FONT_SIZE_TITLE},&H00FFFFFF,&H000000FF,"
        f"&H00000000,&H90000000,-1,0,0,0,100,100,0,0,3,4,0,2,"
        f"{MARGIN_H},{MARGIN_H},{MARGIN_V_TITLE},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )


def build(
    candidates: list[Candidate],
    source_path,
    summary: str | None,
    width: int,
    height: int,
    max_beats: int = MAX_BEATS,
) -> Preview | None:
    """Plan a preview from moments that have already been chosen and ranked.

    Returns None when there is nothing worth assembling. One moment is not a
    preview -- it is the clip that moment already produced, with cards bolted
    on -- so a run that selected a single teaser does not get one.

    Timings are accumulated as the segments are laid out, because the overlay is
    drawn over the *assembled* timeline: a title's position depends on the total
    length of everything before its beat, which is not known until then.
    """
    beats = candidates[:max_beats]
    if len(beats) < 2:
        logger.info(
            "Not assembling a preview from %d moment(s): fewer than two beats "
            "is the clip itself with cards attached",
            len(beats),
        )
        return None

    segments: list[Segment] = [Segment(duration_seconds=OPENING_CARD_SECONDS)]
    events: list[str] = [
        f"Dialogue: 0,{ass_timestamp(0.0)},"
        f"{ass_timestamp(OPENING_CARD_SECONDS)},Card,,0,0,0,,"
        f"{escape_ass_text(headline(summary))}"
    ]

    elapsed = OPENING_CARD_SECONDS
    for candidate in beats:
        # Never longer than the moment itself: a beat that ran past its end
        # would show whatever follows, which was not chosen for anything.
        length = min(BEAT_SECONDS, candidate.duration_seconds)
        segments.append(
            Segment(
                duration_seconds=length,
                source=source_path,
                start_seconds=candidate.start_seconds,
            )
        )
        events.append(
            f"Dialogue: 0,{ass_timestamp(elapsed)},"
            f"{ass_timestamp(elapsed + min(TITLE_SECONDS, length))},"
            f"Title,,0,0,0,,{escape_ass_text(candidate.title)}"
        )
        elapsed += length

    segments.append(Segment(duration_seconds=CLOSING_CARD_SECONDS))
    events.append(
        f"Dialogue: 0,{ass_timestamp(elapsed)},"
        f"{ass_timestamp(elapsed + CLOSING_CARD_SECONDS)},Card,,0,0,0,,"
        f"{escape_ass_text(CLOSING_TEXT)}"
    )

    overlay = _styles(width, height) + "".join(f"{line}\n" for line in events)
    return Preview(segments=segments, overlay=overlay)
