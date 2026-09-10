"""Measuring whether the pipeline is any good.

Everything under `app/services` decides what the product does. Everything here
decides whether those decisions were right, and it is deliberately a separate
package: nothing in the pipeline imports from it, so evaluation can be run,
rewritten, or removed without touching a line of code that serves a request.

Four things live here, in increasing order of what they cost to use:

* `metrics`   -- temporal IoU, greedy matching, Precision/Recall/F1 @ K. Pure
                 arithmetic, no I/O, no dependencies.
* `baselines` -- four alternative ways to pick spans, scored on identical
                 ground truth. Without these an F1 is a number with nothing to
                 compare it to.
* `harness`   -- loads annotations and a run's real output, scores both, and
                 reports the comparison.
* `ablation`  -- the same score with one pipeline component disabled per row,
                 which is the only way to find out whether a component earns
                 its place.

The ground truth itself comes from two places. Files under
`backend/evaluation/ground_truth/` are hand-annotated, and the app's own
`teaser_feedback` table is annotation collected as a side effect of somebody
using the product -- see services/feedback_service.py for why the second is
better data than the first.
"""

from app.evaluation.metrics import (
    GroundTruthSpan,
    RetrievalScores,
    match_pairs,
    retrieval_scores,
    temporal_iou,
)

__all__ = [
    "GroundTruthSpan",
    "RetrievalScores",
    "match_pairs",
    "retrieval_scores",
    "temporal_iou",
]
