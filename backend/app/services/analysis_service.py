"""Validation of AI output.

Gemini output is untrusted input. Nothing reaches FFmpeg until every field has
been checked here (SECURITY.md, FR-009, AI_DESIGN.md).
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.ai.base import (
    MAX_CHAPTERS,
    MAX_HOOK_CHARS,
    MAX_KEYWORD_CHARS,
    MAX_KEYWORDS,
    MAX_REASON_CHARS,
    MAX_SUMMARY_CHARS,
    MAX_TITLE_CHARS,
    RawCandidate,
    RawCandidateList,
)
from app.config import Settings
from app.errors import AppError
from app.services.pipeline_report import CandidateReport, DropReason

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


@dataclass
class Chapter:
    """One validated section of the source video."""

    start_seconds: float
    end_seconds: float
    title: str


@dataclass
class Narrative:
    """What the model said about the video as a whole.

    Separate from the candidates because it fails differently. A moment that
    does not survive validation costs the run a clip; a summary that does not is
    simply absent, and the teasers are unaffected. So nothing here can raise --
    the empty Narrative is a valid one.
    """

    summary: str = ""
    chapters: list[Chapter] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.summary or self.chapters or self.keywords)


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
) -> tuple[str, str] | None:
    """Return (reason slug, detail) for an unusable candidate, or None.

    Two values because the two readers want different things. The detail goes
    in the log, where a human is diagnosing one candidate and wants the numbers.
    The slug is counted across runs, so it must be the same string every time --
    a per-candidate sentence would produce one key with a count of one for each.

    First failure wins, in the order below. A candidate that is both out of
    bounds and too short is counted once, under the more fundamental of the two,
    so the per-reason totals stay interpretable.
    """
    start, end = raw.start_seconds, raw.end_seconds

    if start < 0:
        return DropReason.BOUNDS, f"start {start:.2f}s is negative"
    if end <= start:
        return DropReason.BOUNDS, f"end {end:.2f}s is not after start {start:.2f}s"
    if end > video_duration:
        return DropReason.BOUNDS, (
            f"end {end:.2f}s exceeds the video duration {video_duration:.2f}s"
        )

    length = end - start
    if length < settings.teaser_min_seconds:
        return DropReason.TOO_SHORT, (
            f"length {length:.2f}s is below the {settings.teaser_min_seconds}s minimum"
        )
    if length > max_clip_seconds:
        return DropReason.TOO_LONG, (
            f"length {length:.2f}s is above the {max_clip_seconds}s maximum"
        )

    if not clean_text(raw.title, MAX_TITLE_CHARS):
        return DropReason.EMPTY_TEXT, "title is empty"
    if not clean_text(raw.hook, MAX_HOOK_CHARS):
        return DropReason.EMPTY_TEXT, "hook is empty"
    if not clean_text(raw.reason, MAX_REASON_CHARS):
        return DropReason.EMPTY_TEXT, "reason is empty"
    return None


def validate_candidates(
    raw_list: RawCandidateList,
    settings: Settings,
    video_duration: float,
    max_clip_seconds: int | None = None,
    min_self_contained: float | None = None,
    report: CandidateReport | None = None,
) -> list[Candidate]:
    """Discard every candidate that fails validation, keep the rest.

    Invalid candidates are dropped rather than repaired (AI_DESIGN.md).

    `max_clip_seconds` and `min_self_contained` default to the server settings
    so existing callers are unaffected.

    `report` is filled in as a side effect when one is supplied. An out
    parameter rather than an extra return value, because this function's
    contract is "the candidates that survived, or an exception if none did" and
    a run that fails here still wants the tally of what it dropped -- which a
    tuple return would take away at exactly the moment it is most interesting.
    """
    ceiling = max_clip_seconds or settings.teaser_max_seconds
    floor = (
        settings.teaser_min_self_contained
        if min_self_contained is None
        else min_self_contained
    )
    tally = report if report is not None else CandidateReport()
    tally.proposed = len(raw_list.candidates)

    valid: list[Candidate] = []
    rejected: list[str] = []

    for index, raw in enumerate(raw_list.candidates):
        outcome = _reject_reason(raw, settings, video_duration, ceiling)
        if outcome is not None:
            slug, detail = outcome
            tally.drop(slug)
            rejected.append(f"#{index + 1} ({raw.start_seconds:.1f}s): {detail}")
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

    return _keep_self_contained(valid, floor, tally)


def validate_narrative(
    raw_list: RawCandidateList, video_duration: float
) -> Narrative:
    """Clean the whole-video fields. Never raises.

    Held to the same standard as the candidates -- every string normalised and
    capped, every timestamp checked against the real duration, anything that
    fails discarded rather than repaired -- but not to the same consequence.
    These fields describe the video; they do not become a file on disk or an
    argument to a subprocess. A run that produced good clips and a malformed
    chapter list is a run with good clips.
    """
    summary = clean_text(raw_list.summary or "", MAX_SUMMARY_CHARS)

    keywords: list[str] = []
    seen: set[str] = set()
    for raw_keyword in raw_list.keywords or []:
        keyword = clean_text(str(raw_keyword), MAX_KEYWORD_CHARS)
        # Case-insensitive, because "RAG" and "rag" are one keyword to a reader
        # and two to a set. The first spelling wins.
        folded = keyword.casefold()
        if not keyword or folded in seen:
            continue
        seen.add(folded)
        keywords.append(keyword)
        if len(keywords) >= MAX_KEYWORDS:
            break

    chapters: list[Chapter] = []
    rejected: list[str] = []
    for index, raw_chapter in enumerate(raw_list.chapters or []):
        title = clean_text(raw_chapter.title, MAX_TITLE_CHARS)
        start, end = raw_chapter.start_seconds, raw_chapter.end_seconds

        if not title:
            rejected.append(f"#{index + 1}: title is empty")
        elif start < 0:
            rejected.append(f"#{index + 1}: start {start:.2f}s is negative")
        elif end <= start:
            rejected.append(
                f"#{index + 1}: end {end:.2f}s is not after start {start:.2f}s"
            )
        elif start > video_duration:
            rejected.append(
                f"#{index + 1}: start {start:.2f}s is past the end of the video"
            )
        else:
            chapters.append(
                Chapter(
                    start_seconds=round(start, 3),
                    # A chapter overrunning the end is clamped rather than
                    # dropped: unlike a clip window, the only thing downstream
                    # of this is a contents entry, and losing the last section
                    # of the video tells the reader less than trimming it does.
                    end_seconds=round(min(end, video_duration), 3),
                    title=title,
                )
            )
        if len(chapters) >= MAX_CHAPTERS:
            break

    chapters.sort(key=lambda chapter: chapter.start_seconds)

    if rejected:
        logger.warning(
            "Discarded %d of %d chapters: %s",
            len(rejected), len(raw_list.chapters or []), "; ".join(rejected),
        )
    if not summary:
        logger.info("The AI returned no usable summary for this run.")

    return Narrative(summary=summary, chapters=chapters, keywords=keywords)


def _keep_self_contained(
    candidates: list[Candidate],
    threshold: float,
    report: CandidateReport | None = None,
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

    if report is not None:
        for _ in dropped:
            report.drop(DropReason.NOT_SELF_CONTAINED)

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
