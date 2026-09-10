"""One component disabled per row: does each part earn its place?

Baselines show the pipeline beats the alternatives. They say nothing about
whether any individual rule inside it is doing work. A self-containment floor,
a minimum gap, a set of scoring weights and three recording profiles are all
tuned numbers that were chosen by judgment, and every one of them could be
neutral or harmful without anything in the system noticing.

This re-runs *selection only* against candidates a real run already produced.
No model call, no FFmpeg, no new clips -- so a full ablation costs nothing and
can be run on every prompt change. The price of that is what it cannot measure:
anything upstream of selection (the prompt, the recording-type guidance, the
audience conditioning) would need a fresh analysis to ablate, and those rows say
so rather than reporting a delta of zero.

Reporting a delta of zero for something that was never measured is the specific
failure this module is written to avoid. Zero reads as "this component does not
matter", which is the opposite claim from "we did not test it".
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.evaluation.harness import GroundTruth, Span
from app.evaluation.metrics import DEFAULT_KS, RetrievalScores, retrieval_scores
from app.services.analysis_service import Candidate
from app.services.ranking_service import SCORE_WEIGHTS, select_top

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ablation:
    """One row: a named component, and how selection behaves without it."""

    name: str
    description: str
    #: None for rows that cannot be measured from cached candidates alone.
    needs: str | None = None


ABLATIONS: tuple[Ablation, ...] = (
    Ablation("none", "The pipeline as it ships"),
    Ablation(
        "self_contained_floor",
        "Keep fragments the floor would have discarded",
    ),
    Ablation(
        "min_gap",
        "Allow selected moments to sit next to each other",
    ),
    Ablation(
        "score_weights",
        "Rank on the unweighted mean of the dimensions instead",
    ),
    Ablation(
        "ranking",
        "Take the first N candidates in the order the model returned them",
    ),
    Ablation(
        "recording_profile",
        "Apply the webinar constants to every recording type",
        needs="a fresh analysis per recording type; the profile also shapes the prompt",
    ),
    Ablation(
        "audience_conditioning",
        "Ask for moments without naming the audience",
        needs="a fresh analysis with the audience withheld; costs one call per audience",
    ),
    Ablation(
        "snapping",
        "Leave every cut point where ranking put it",
        needs="re-cutting the clips; measured instead by clean_cut_rate in the run report",
    ),
)


@dataclass
class AblationRow:
    name: str
    description: str
    available: bool = True
    unavailable_reason: str = ""
    scores: dict[int, RetrievalScores] = field(default_factory=dict)
    selected: list[Span] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        if not self.available:
            return {
                "name": self.name,
                "description": self.description,
                "available": False,
                "reason": self.unavailable_reason,
            }
        return {
            "name": self.name,
            "description": self.description,
            "available": True,
            "selected": len(self.selected),
            "scores": {k: s.to_dict() for k, s in sorted(self.scores.items())},
        }


def _spans(candidates: list[Candidate]) -> list[Span]:
    return [(c.start_seconds, c.end_seconds) for c in candidates]


def _without_score_weights(candidates: list[Candidate]) -> list[Candidate]:
    """Copies scored on the plain mean of their dimensions.

    Copies, not mutations. `Candidate.score` is written in place by
    rank_candidates, so ablating the weights on the shared objects would leave
    every later row scoring against the ablated values -- the ablation would
    contaminate the control.
    """
    clones = []
    for candidate in candidates:
        clone = Candidate(
            start_seconds=candidate.start_seconds,
            end_seconds=candidate.end_seconds,
            title=candidate.title,
            hook=candidate.hook,
            reason=candidate.reason,
            scores=dict(candidate.scores),
        )
        present = [clone.scores.get(name, 0.0) for name in SCORE_WEIGHTS]
        clone.scores = {
            **clone.scores,
            # Overwriting every dimension with the same value makes the weighted
            # sum equal that value, whatever the weights are -- which is exactly
            # "rank as though the weights were uniform", expressed without
            # reaching into ranking_service.
            **{name: sum(present) / len(present) for name in SCORE_WEIGHTS},
        }
        clones.append(clone)
    return clones


def run(
    candidates: list[Candidate],
    truth: GroundTruth,
    count: int,
    min_gap_seconds: float,
    min_self_contained: float,
    ks: tuple[int, ...] = DEFAULT_KS,
) -> list[AblationRow]:
    """Score every ablation against one asset's annotations.

    `candidates` must be the *unfiltered* validated set -- everything analysis
    proposed that had usable timestamps and text, including the fragments the
    self-containment floor would drop. Passing the already-filtered list would
    make the `self_contained_floor` row identical to the control and report the
    floor as having no effect.
    """
    rows: list[AblationRow] = []

    def add(name: str, description: str, selected: list[Candidate]) -> None:
        row = AblationRow(name=name, description=description)
        row.selected = _spans(selected)
        row.scores = {k: retrieval_scores(row.selected, truth.spans, k) for k in ks}
        rows.append(row)

    kept = [
        c for c in candidates
        if c.scores.get("self_contained", 0.0) >= min_self_contained
    ]

    for ablation in ABLATIONS:
        if ablation.needs is not None:
            rows.append(
                AblationRow(
                    name=ablation.name,
                    description=ablation.description,
                    available=False,
                    unavailable_reason=ablation.needs,
                )
            )
            continue

        if ablation.name == "none":
            add(ablation.name, ablation.description,
                select_top(kept, count, min_gap_seconds))
        elif ablation.name == "self_contained_floor":
            add(ablation.name, ablation.description,
                select_top(candidates, count, min_gap_seconds))
        elif ablation.name == "min_gap":
            add(ablation.name, ablation.description, select_top(kept, count, 0.0))
        elif ablation.name == "score_weights":
            add(ablation.name, ablation.description,
                select_top(_without_score_weights(kept), count, min_gap_seconds))
        elif ablation.name == "ranking":
            # Model order, gap rule still applied: this ablates the ranking, not
            # the separation rule, and dropping both at once would not say which
            # of the two the difference came from.
            unranked = []
            for candidate in kept:
                if len(unranked) >= count:
                    break
                if all(
                    not (candidate.start_seconds < chosen.end_seconds + min_gap_seconds
                         and chosen.start_seconds - min_gap_seconds < candidate.end_seconds)
                    for chosen in unranked
                ):
                    unranked.append(candidate)
            add(ablation.name, ablation.description, unranked)

    return rows


def deltas(rows: list[AblationRow], k: int) -> dict[str, Any]:
    """Each available row's precision at K, and its gap from the control.

    A negative delta means the pipeline is better with that component than
    without it -- which is the result that justifies the component. A positive
    delta means removing it *improved* the score, and that is the finding worth
    acting on rather than explaining away.
    """
    control = next((r for r in rows if r.name == "none" and r.available), None)
    if control is None or k not in control.scores:
        return {"k": k, "control": None, "rows": {}}

    baseline = control.scores[k].precision
    return {
        "k": k,
        "control": round(baseline, 4),
        "rows": {
            row.name: (
                {"available": False, "reason": row.unavailable_reason}
                if not row.available
                else {
                    "available": True,
                    "precision": round(row.scores[k].precision, 4),
                    "delta": round(row.scores[k].precision - baseline, 4),
                }
            )
            for row in rows
            if row.name != "none"
        },
    }
