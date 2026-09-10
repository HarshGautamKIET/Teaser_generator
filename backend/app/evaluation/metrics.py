"""Retrieval metrics for span selection.

Two definitions here are not the most natural reading of their names, and both
differences are the point.

**Precision@K divides by K, not by the number of predictions made.** A run asked
for five clips that returns two is penalised, not scored as though it answered
perfectly with a short list. Dividing by the prediction count would make
"return one clip you are sure of" the highest-scoring strategy available, which
is not a teaser generator.

**A match requires tIoU >= 0.5, and each annotated span can be claimed once.**
Overlapping by a second is not "found the moment" -- without the threshold, any
prediction landing anywhere near a busy region of the video counts as a hit.
And without the one-claim rule, a system returning the same strong moment five
times scores a perfect Precision@5, which is precisely the degenerate strategy
these metrics exist not to reward.

Pure arithmetic. No I/O, no database, no FFmpeg -- so this module is testable
without any of them, and the tests that pin these definitions run in
milliseconds.
"""

from collections.abc import Sequence
from dataclasses import dataclass

Span = tuple[float, float]

#: Below this, two spans that overlap are not the same moment. Half the union is
#: already generous for a 45-second clip: it admits a prediction that is 15
#: seconds early on a 45-second annotation.
MATCH_IOU = 0.5

#: Reported alongside the headline. A 45-second teaser holds three to five
#: clips, so K=3 is what this product actually asks for and K=5 is the number
#: comparable with the wider literature.
DEFAULT_KS = (1, 3, 5)


@dataclass(frozen=True)
class GroundTruthSpan:
    """One annotated moment: a span that a good run should have selected.

    `strength` is the annotator's confidence from 1 to 3. It is carried rather
    than used by the plain metrics, so that a weighted variant can be added
    without re-annotating -- missing a "must include" should eventually cost
    more than missing a "usable", and that is impossible to compute later if the
    distinction was never recorded.
    """

    start: float
    end: float
    why: str = ""
    audience: str = "general"
    strength: int = 2

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(
                f"A ground-truth span must end after it starts: "
                f"[{self.start}, {self.end}]"
            )
        if not 1 <= self.strength <= 3:
            raise ValueError(f"strength must be 1-3, got {self.strength}")

    @property
    def span(self) -> Span:
        return (self.start, self.end)


@dataclass(frozen=True)
class RetrievalScores:
    """One row of a results table."""

    k: int
    precision: float
    recall: float
    f1: float
    mean_iou: float
    matched: int
    predicted: int
    annotated: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "k": self.k,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "mean_iou": round(self.mean_iou, 4),
            "matched": self.matched,
            "predicted": self.predicted,
            "annotated": self.annotated,
        }


def temporal_iou(a: Span, b: Span) -> float:
    """Intersection over union of two time spans, in [0, 1]."""
    intersection = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - intersection
    return intersection / union if union > 0 else 0.0


def match_pairs(
    predictions: Sequence[Span],
    truth: Sequence[GroundTruthSpan],
    threshold: float = MATCH_IOU,
) -> list[tuple[int, int, float]]:
    """Pair predictions to annotations, best overlap first, one claim each.

    Greedy rather than optimal (Hungarian). The assignment that maximises total
    overlap can differ from this one, but only when two predictions contest the
    same annotation -- and in that case the run has duplicated a moment, which
    should cost it rather than be optimised away.

    Ties are broken by index so the result does not depend on dictionary or set
    ordering: this number goes in a CI gate, and a metric that moves between
    identical runs is a metric that gets switched off.

    Returns (prediction index, truth index, iou) for each accepted pair.
    """
    scored = sorted(
        (
            (temporal_iou(prediction, span.span), -p_index, -t_index)
            for p_index, prediction in enumerate(predictions)
            for t_index, span in enumerate(truth)
        ),
        reverse=True,
    )

    used_predictions: set[int] = set()
    used_truth: set[int] = set()
    pairs: list[tuple[int, int, float]] = []
    for iou, negative_p, negative_t in scored:
        if iou < threshold:
            break
        p_index, t_index = -negative_p, -negative_t
        if p_index in used_predictions or t_index in used_truth:
            continue
        used_predictions.add(p_index)
        used_truth.add(t_index)
        pairs.append((p_index, t_index, iou))
    return pairs


def retrieval_scores(
    predictions: Sequence[Span],
    truth: Sequence[GroundTruthSpan],
    k: int,
    threshold: float = MATCH_IOU,
) -> RetrievalScores:
    """Precision / Recall / F1 @ K, plus mean tIoU over the matched pairs.

    Recall is reported rather than optimised. A teaser set containing every
    worthy moment in a two-hour talk is not a good teaser set, it is a summary,
    so a run that scores 1.0 here has probably failed at the actual task.
    Precision is the headline.
    """
    considered = list(predictions[:k])
    pairs = match_pairs(considered, truth, threshold)

    precision = len(pairs) / k if k else 0.0
    recall = len(pairs) / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    # Averaged over matched pairs only. Folding in a zero for every unmatched
    # prediction would blend "did it find the moment" into "did it cut the
    # moment well", and those are the two questions this pair of numbers exists
    # to keep apart.
    mean_iou = sum(iou for _, _, iou in pairs) / len(pairs) if pairs else 0.0

    return RetrievalScores(
        k=k,
        precision=precision,
        recall=recall,
        f1=f1,
        mean_iou=mean_iou,
        matched=len(pairs),
        predicted=len(considered),
        annotated=len(truth),
    )


