"""What a run discarded, and how well it cut what it kept.

The pipeline has always thrown things away. Candidates whose timestamps do not
fit the video, moments that need surrounding context, boundaries with no pause
near enough to snap to -- each of those is a decision, each was already correct,
and each was recorded only as a log line.

That is the difference between validating model output and being able to say
anything about it. A run that proposed eight moments and kept one is a run whose
prompt is wrong for this source; a run that kept all eight is working. Both
looked identical from outside, because the only number the system reported was
how many clips came out.

Nothing here changes a pipeline decision. Every drop below was already
happening; this module gives it a stable name and counts it.

Design note: the reasons are slugs, not sentences. They become keys in a jsonb
column and are counted across runs, so "length 4.20s is below the 20s minimum"
-- which is the right thing to put in a log -- would produce a distinct key per
candidate and a count of one for each.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class DropReason:
    """Why a proposed moment did not become a clip.

    Ordered from most to least fundamental, which is also the order the checks
    run in. A candidate is counted once, under the first thing it broke, so the
    per-reason totals stay readable: a candidate that is both out of bounds and
    too short says nothing useful about clip length.
    """

    # Validation (analysis_service).
    BOUNDS = "bounds"                    # outside [0, duration], or end <= start
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    EMPTY_TEXT = "empty_text"            # no title, hook, or reason
    NOT_SELF_CONTAINED = "not_self_contained"

    # Selection (ranking_service). These are not failures -- a moment dropped
    # here was valid and simply lost -- but they belong in the same tally,
    # because "why did I get one clip" has the same answer shape either way.
    TOO_CLOSE = "too_close"              # inside the minimum gap of a better one
    OUTRANKED = "outranked"              # valid, separated, but not top-N


@dataclass
class CandidateReport:
    """The tally of what analysis proposed and what survived it."""

    proposed: int = 0
    dropped: dict[str, int] = field(default_factory=dict)

    def drop(self, reason: str) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + 1

    @property
    def total_dropped(self) -> int:
        return sum(self.dropped.values())

    @property
    def kept(self) -> int:
        # Derived rather than tracked. A stored `kept` and a stored `dropped`
        # can disagree with `proposed`, and this number is quoted; it has to be
        # a consequence of the tally rather than a parallel record of it.
        return max(0, self.proposed - self.total_dropped)

    @property
    def drop_rate(self) -> float:
        return self.total_dropped / self.proposed if self.proposed else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed": self.proposed,
            "kept": self.kept,
            "dropped": dict(sorted(self.dropped.items())),
            "drop_rate": round(self.drop_rate, 4),
        }


@dataclass
class SnapReport:
    """Whether cutting on a pause actually did anything.

    Snapping is the pipeline's most easily-believed feature: it is described in
    the README, it has tests, and it can still be doing nothing at all on real
    sources if no boundary ever has a pause within the shift window. Declining
    to move is a correct outcome, so the failure this counts is not "a boundary
    stayed put" but "every boundary stayed put".
    """

    starts_moved: int = 0
    starts_kept: int = 0
    ends_moved: int = 0
    ends_kept: int = 0
    # Signed, in seconds. Kept individually so the mean is computed from the
    # data and a later percentile does not need a schema change.
    shifts: list[float] = field(default_factory=list)

    @property
    def moved(self) -> int:
        return self.starts_moved + self.ends_moved

    @property
    def considered(self) -> int:
        return self.moved + self.starts_kept + self.ends_kept

    @property
    def move_rate(self) -> float:
        return self.moved / self.considered if self.considered else 0.0

    @property
    def mean_abs_shift_seconds(self) -> float:
        return sum(abs(s) for s in self.shifts) / len(self.shifts) if self.shifts else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "starts_moved": self.starts_moved,
            "starts_kept": self.starts_kept,
            "ends_moved": self.ends_moved,
            "ends_kept": self.ends_kept,
            "move_rate": round(self.move_rate, 4),
            "mean_abs_shift_seconds": round(self.mean_abs_shift_seconds, 3),
        }


@dataclass
class CutQuality:
    """How cleanly one clip begins, measured rather than judged.

    `opening_delta_db` is the first fraction of a second relative to the clip's
    own average loudness. A clip that opens mid-word opens at about the level of
    the rest of it, so the delta is near zero; a clip that opens on a pause
    opens well below it, so the delta is strongly negative.

    Relative, not absolute, because an absolute threshold would measure the
    recording's gain rather than the cut: a quietly-recorded talk would score as
    all-clean and a loud one as all-broken.
    """

    teaser_id: str
    opening_db: float
    clip_db: float
    threshold_db: float

    @property
    def delta_db(self) -> float:
        return round(self.opening_db - self.clip_db, 2)

    @property
    def clean(self) -> bool:
        return self.delta_db <= self.threshold_db

    def to_dict(self) -> dict[str, Any]:
        return {
            "teaser_id": self.teaser_id,
            "opening_db": round(self.opening_db, 2),
            "clip_db": round(self.clip_db, 2),
            "delta_db": self.delta_db,
            "clean": self.clean,
        }


@dataclass
class PipelineReport:
    """Everything a run can say about itself beyond the clips it produced.

    Assembled during the run and written once at the end, onto Job.
    pipeline_report. Never raises and never blocks: a run whose report could not
    be built is a run with clips and no report, which is exactly how the
    narrative fields already behave.
    """

    candidates: CandidateReport = field(default_factory=CandidateReport)
    snap: SnapReport = field(default_factory=SnapReport)
    cuts: list[CutQuality] = field(default_factory=list)
    # Honest degradation. Anything the run could not do but carried on without,
    # tagged so the reason survives past the log. Silent degradation is the one
    # outcome this project treats as unacceptable, and until now "the preview
    # failed to assemble" left no trace on the run at all.
    degraded: list[str] = field(default_factory=list)

    def degrade(self, tag: str) -> None:
        if tag not in self.degraded:
            self.degraded.append(tag)
        logger.info("Run degraded: %s", tag)

    @property
    def clean_cut_rate(self) -> float:
        measured = [cut for cut in self.cuts if cut is not None]
        if not measured:
            return 0.0
        return sum(1 for cut in measured if cut.clean) / len(measured)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": self.candidates.to_dict(),
            "snap": self.snap.to_dict(),
            "cuts": [cut.to_dict() for cut in self.cuts],
            "clean_cut_rate": round(self.clean_cut_rate, 4),
            "degraded": list(self.degraded),
        }
