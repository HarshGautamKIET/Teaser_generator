"""Validation of AI output.

Gemini output is untrusted input. Nothing reaches FFmpeg until every field has
been checked here (SECURITY.md, FR-009, AI_DESIGN.md).
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.ai.base import (
    MAX_HOOK_CHARS,
    MAX_REASON_CHARS,
    MAX_TITLE_CHARS,
    RawCandidate,
    RawCandidateList,
)
from app.config import Settings
from app.errors import AppError

logger = logging.getLogger(__name__)

_WHITESPACE = re.compile(r"\s+")


class NoValidCandidatesError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("NO_VALID_CANDIDATES", message, 422)


class NoSelfContainedMomentsError(AppError):
    """Moments were found, but none of them stood on their own.

    Distinct from NO_VALID_CANDIDATES on purpose: "the AI found nothing usable"
    and "everything it found was a fragment" call for different fixes, and
    collapsing them would tell the reader to change the wrong thing.
    """

    def __init__(self, message: str) -> None:
        super().__init__("NO_SELF_CONTAINED_MOMENTS", message, 422)


@dataclass
class Candidate:
    """A validated moment. Timestamps here are known to be safe."""

    start_seconds: float
    end_seconds: float
    title: str
    hook: str
    reason: str
    scores: dict[str, float] = field(default_factory=dict)
    score: float = 0.0

    @property
    def duration_seconds(self) -> float:
        return round(self.end_seconds - self.start_seconds, 3)

    def overlaps(self, other: "Candidate") -> bool:
        return (
            self.start_seconds < other.end_seconds
            and other.start_seconds < self.end_seconds
        )


def clean_text(value: str, max_chars: int) -> str:
    """Normalise an untrusted AI string and cap its length.

    Control characters are stripped so nothing odd reaches logs or the UI.
    """
    # Control characters become spaces so words are not silently joined.
    cleaned = "".join(
        " " if unicodedata.category(ch).startswith("C") else ch for ch in value
    )
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip() + "\u2026"
    return cleaned


def clean_scores(scores: dict[str, float]) -> dict[str, float]:
    """Clamp AI scores into the documented 0-10 range."""
    cleaned = {}
    for name, value in scores.items():
        clamped = min(10.0, max(0.0, float(value)))
        if clamped != value:
            logger.warning("Clamped AI score %s from %s to %s", name, value, clamped)
        cleaned[name] = clamped
    return cleaned


def _reject_reason(
    raw: RawCandidate,
    settings: Settings,
    video_duration: float,
    max_clip_seconds: int,
) -> str | None:
    """Return why this candidate is unusable, or None if it is fine."""
    start, end = raw.start_seconds, raw.end_seconds

    if start < 0:
        return f"start {start:.2f}s is negative"
    if end <= start:
        return f"end {end:.2f}s is not after start {start:.2f}s"
    if end > video_duration:
        return f"end {end:.2f}s exceeds the video duration {video_duration:.2f}s"

    length = end - start
    if length < settings.teaser_min_seconds:
        return f"length {length:.2f}s is below the {settings.teaser_min_seconds}s minimum"
    if length > max_clip_seconds:
        return f"length {length:.2f}s is above the {max_clip_seconds}s maximum"

    if not clean_text(raw.title, MAX_TITLE_CHARS):
        return "title is empty"
    if not clean_text(raw.hook, MAX_HOOK_CHARS):
        return "hook is empty"
    if not clean_text(raw.reason, MAX_REASON_CHARS):
        return "reason is empty"
    return None


def validate_candidates(
    raw_list: RawCandidateList,
    settings: Settings,
    video_duration: float,
    max_clip_seconds: int | None = None,
    min_self_contained: float | None = None,
) -> list[Candidate]:
    """Discard every candidate that fails validation, keep the rest.

    Invalid candidates are dropped rather than repaired (AI_DESIGN.md).

    `max_clip_seconds` and `min_self_contained` default to the server settings
    so existing callers are unaffected.
    """
    ceiling = max_clip_seconds or settings.teaser_max_seconds
    floor = (
        settings.teaser_min_self_contained
        if min_self_contained is None
        else min_self_contained
    )
    valid: list[Candidate] = []
    rejected: list[str] = []

    for index, raw in enumerate(raw_list.candidates):
        reason = _reject_reason(raw, settings, video_duration, ceiling)
        if reason is not None:
            rejected.append(f"#{index + 1} ({raw.start_seconds:.1f}s): {reason}")
            continue

        valid.append(
            Candidate(
                start_seconds=round(raw.start_seconds, 3),
                end_seconds=round(raw.end_seconds, 3),
                title=clean_text(raw.title, MAX_TITLE_CHARS),
                hook=clean_text(raw.hook, MAX_HOOK_CHARS),
                reason=clean_text(raw.reason, MAX_REASON_CHARS),
                scores=clean_scores(raw.scores.model_dump()),
            )
        )

    if rejected:
        logger.warning(
            "Discarded %d of %d AI candidates: %s",
            len(rejected), len(raw_list.candidates), "; ".join(rejected),
        )
    logger.info(
        "Validated %d of %d AI candidates", len(valid), len(raw_list.candidates)
    )

    if not valid:
        raise NoValidCandidatesError(
            "The AI did not return any moments that fit this video and the "
            "configured teaser length."
        )

    return _keep_self_contained(valid, floor)


def _keep_self_contained(
    candidates: list[Candidate], threshold: float
) -> list[Candidate]:
    """Drop moments that do not stand on their own.

    A filter rather than a weight. Self-containment was previously worth 10% of
    the ranking score, which meant a fragment with a strong hook still won --
    hook carries three times the weight. A teaser that opens mid-thought is not
    a slightly worse teaser, it is not one, so it is removed from contention
    entirely instead of being allowed to out-score its way in.
    """
    if threshold <= 0:
        return candidates

    kept, dropped = [], []
    for candidate in candidates:
        score = candidate.scores.get("self_contained", 0.0)
        (kept if score >= threshold else dropped).append((candidate, score))

    if dropped:
        logger.info(
            "Discarded %d moment(s) that needed surrounding context: %s",
            len(dropped),
            "; ".join(
                f"{candidate.start_seconds:.1f}s (self_contained {score:.1f})"
                for candidate, score in dropped
            ),
        )

    if not kept:
        raise NoSelfContainedMomentsError(
            f"The AI found {len(candidates)} moment(s), but none of them stood on "
            "their own -- each needed surrounding context to make sense. Try a "
            "longer maximum clip length, or a different audience."
        )
    return [candidate for candidate, _ in kept]
