"""Candidate scoring and selection.

The backend -- not the AI -- decides the final ordering. Gemini supplies
per-dimension scores; the weights and the selection rules live here (FR-010).
"""

import logging

from app.services.analysis_service import Candidate
from app.services.pipeline_report import CandidateReport, DropReason

logger = logging.getLogger(__name__)

# Weights from AI_DESIGN.md. They must sum to 1.0.
SCORE_WEIGHTS: dict[str, float] = {
    "hook": 0.30,
    "audience_relevance": 0.25,
    "information_value": 0.20,
    "engagement": 0.15,
    "self_contained": 0.10,
}

assert abs(sum(SCORE_WEIGHTS.values()) - 1.0) < 1e-9, "score weights must sum to 1.0"


def compute_score(scores: dict[str, float]) -> float:
    """Weighted 0-10 score. A missing dimension contributes nothing."""
    total = sum(scores.get(name, 0.0) * weight for name, weight in SCORE_WEIGHTS.items())
    return round(total, 3)


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Score every candidate and order them best-first.

    Ties break toward the earlier moment, so ordering is deterministic.
    """
    for candidate in candidates:
        candidate.score = compute_score(candidate.scores)

    ranked = sorted(candidates, key=lambda c: (-c.score, c.start_seconds))
    logger.info(
        "Ranked %d candidates; best=%.2f worst=%.2f",
        len(ranked), ranked[0].score, ranked[-1].score,
    )
    return ranked


def separation_seconds(first: Candidate, second: Candidate) -> float:
    """Gap between two moments. Negative when they overlap."""
    return max(
        second.start_seconds - first.end_seconds,
        first.start_seconds - second.end_seconds,
    )


def affordable_gap(
    configured_gap: float,
    video_duration: float,
    count: int,
    min_clip_seconds: float,
) -> float:
    """Shrink the requested gap to what this video can actually spare.

    A fixed gap does not survive contact with short sources. Fifteen seconds is
    nothing in a forty-minute talk and fatal in a ninety-second one: three
    twenty-five second clips plus two fifteen second gaps need 105 seconds, so
    the run silently returns one clip instead of three and the reason is buried
    in a debug log.

    So the gap is treated as a preference bounded by arithmetic. Whatever is
    left after the clips themselves is divided between the gaps, and the
    configured value applies only if it fits. A video with nothing to spare
    falls back to plain non-overlap, which is the most separation it can
    honestly offer.
    """
    if count <= 1 or configured_gap <= 0:
        return 0.0

    spare = video_duration - count * min_clip_seconds
    if spare <= 0:
        return 0.0
    return max(0.0, min(configured_gap, spare / (count - 1)))


def select_top(
    candidates: list[Candidate],
    count: int,
    min_gap_seconds: float = 0.0,
    report: CandidateReport | None = None,
) -> list[Candidate]:
    """Take the best `count` candidates, keeping them apart from each other.

    Non-overlap alone is not enough for clips that have to stand alone. Two
    adjacent moments -- one ending at 0:30, the next starting at 0:30 -- never
    show the same footage twice and are still one continuous passage cut in
    half, so the second opens on the back half of a sentence the viewer did not
    hear. Requiring a gap makes them separate thoughts rather than merely
    separate files.

    A gap of 0 reduces to the previous non-overlap behaviour.

    `report` is tallied as a side effect when supplied, for the same reason
    validate_candidates takes one. Losing here is not a failure -- an outranked
    moment was perfectly valid -- but it belongs in the same tally, because "why
    did I only get one clip" has one answer shape whether the moment was
    rejected or merely beaten.
    """
    if count <= 0:
        return []

    selected: list[Candidate] = []
    ranked = rank_candidates(candidates)
    # Read before the loop, so a report reused across calls (the ablation runner
    # scores several selections against one tally) counts this call's rejections
    # rather than every call's.
    too_close_before = 0 if report is None else report.dropped.get(
        DropReason.TOO_CLOSE, 0
    )
    for candidate in ranked:
        if len(selected) >= count:
            break

        too_close = next(
            (
                chosen for chosen in selected
                if separation_seconds(chosen, candidate) < min_gap_seconds
            ),
            None,
        )
        if too_close is not None:
            if report is not None:
                report.drop(DropReason.TOO_CLOSE)
            logger.debug(
                "Skipping candidate at %.1fs: %.1fs from the moment at %.1fs "
                "(minimum %.1fs)",
                candidate.start_seconds,
                separation_seconds(too_close, candidate),
                too_close.start_seconds,
                min_gap_seconds,
            )
            continue
        selected.append(candidate)

    if report is not None:
        # Whatever the loop never reached, plus anything it reached after the
        # quota was full. Counted from the arithmetic rather than inside the
        # loop, which `break`s early and would undercount by exactly the tail it
        # skipped -- the part being measured.
        rejected_here = report.dropped.get(DropReason.TOO_CLOSE, 0) - too_close_before
        outranked = len(ranked) - len(selected) - rejected_here
        for _ in range(max(0, outranked)):
            report.drop(DropReason.OUTRANKED)

    if len(selected) < count:
        logger.warning(
            "Only %d sufficiently separated moments available (wanted %d, "
            "minimum gap %.1fs)",
            len(selected), count, min_gap_seconds,
        )
    return selected
