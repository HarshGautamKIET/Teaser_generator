"""The retrieval metrics.

Two definitions here are not the most natural reading of their names, and both
choices are load-bearing -- these numbers go in a CI gate, so a metric that can
be gamed is a gate that will be. Each of those choices gets a test that fails if
someone "simplifies" it back to the obvious version.

Pure arithmetic, so none of this needs a database, FFmpeg, or a model.
"""

import pytest

from app.evaluation.metrics import (
    GroundTruthSpan,
    match_pairs,
    retrieval_scores,
    temporal_iou,
)


def truth(start, end, strength=2):
    return GroundTruthSpan(start=start, end=end, strength=strength)


# ----------------------------------------------------------------------
# temporal_iou
# ----------------------------------------------------------------------
def test_identical_spans_score_one():
    assert temporal_iou((10.0, 50.0), (10.0, 50.0)) == 1.0


def test_disjoint_spans_score_zero():
    assert temporal_iou((10.0, 20.0), (30.0, 40.0)) == 0.0


def test_touching_spans_score_zero():
    """Ending exactly where the next begins is not overlap."""
    assert temporal_iou((10.0, 20.0), (20.0, 30.0)) == 0.0


def test_half_overlap():
    # Intersection 10, union 30.
    assert temporal_iou((0.0, 20.0), (10.0, 30.0)) == pytest.approx(10 / 30)


def test_iou_is_symmetric():
    a, b = (12.0, 47.0), (20.0, 60.0)
    assert temporal_iou(a, b) == temporal_iou(b, a)


# ----------------------------------------------------------------------
# match_pairs -- the one-claim rule
# ----------------------------------------------------------------------
def test_each_annotation_can_be_claimed_only_once():
    """The degenerate strategy these metrics exist not to reward.

    A system that returns the same strong moment five times has found one
    moment. Without the one-claim rule it scores a perfect Precision@5, and
    "return your best guess five times" becomes the optimal play.
    """
    same = (100.0, 140.0)
    pairs = match_pairs([same, same, same], [truth(100.0, 140.0)])

    assert len(pairs) == 1


def test_best_overlap_wins_the_claim():
    predictions = [(100.0, 130.0), (100.0, 141.0)]
    pairs = match_pairs(predictions, [truth(100.0, 140.0)])

    assert len(pairs) == 1
    # The second prediction overlaps more, so it takes the annotation even
    # though the first was offered it earlier.
    assert pairs[0][0] == 1


def test_overlap_below_the_threshold_is_not_a_match():
    """Overlapping by a moment is not "found the moment"."""
    # Intersection 10, union 70 -> 0.14, well under 0.5.
    assert match_pairs([(0.0, 40.0)], [truth(30.0, 70.0)]) == []


def test_matching_is_deterministic():
    """A metric that moves between identical runs is a gate that gets removed."""
    predictions = [(10.0, 50.0), (10.0, 50.0), (200.0, 240.0)]
    annotations = [truth(10.0, 50.0), truth(200.0, 240.0)]

    first = match_pairs(predictions, annotations)
    for _ in range(20):
        assert match_pairs(predictions, annotations) == first


# ----------------------------------------------------------------------
# retrieval_scores -- precision divides by K
# ----------------------------------------------------------------------
def test_precision_divides_by_k_not_by_predictions():
    """Answering with a short list must not score as a perfect answer.

    One correct clip when five were asked for is 0.2, not 1.0. Dividing by the
    number of predictions would make "return one clip you are sure of" the
    highest-scoring strategy available, which is not a teaser generator.
    """
    scores = retrieval_scores([(100.0, 140.0)], [truth(100.0, 140.0)], k=5)

    assert scores.precision == pytest.approx(0.2)
    assert scores.matched == 1


def test_precision_at_k_only_considers_the_first_k():
    predictions = [(0.0, 40.0), (500.0, 540.0), (100.0, 140.0)]
    annotations = [truth(100.0, 140.0)]

    # The match is third, so it is outside K=2 and inside K=3.
    assert retrieval_scores(predictions, annotations, k=2).matched == 0
    assert retrieval_scores(predictions, annotations, k=3).matched == 1


def test_recall_is_over_every_annotation():
    annotations = [truth(100.0, 140.0), truth(300.0, 340.0), truth(500.0, 540.0)]
    scores = retrieval_scores([(100.0, 140.0)], annotations, k=3)

    assert scores.recall == pytest.approx(1 / 3)


def test_mean_iou_ignores_unmatched_predictions():
    """"Did it find the moment" and "did it cut it well" stay separate.

    Averaging a zero in for every miss would blend the two, and a run that found
    one moment perfectly would report a mediocre tIoU because of the moments it
    did not find -- which mean_iou is not measuring.
    """
    predictions = [(100.0, 140.0), (900.0, 940.0)]
    scores = retrieval_scores(predictions, [truth(100.0, 140.0)], k=2)

    assert scores.mean_iou == pytest.approx(1.0)
    assert scores.precision == pytest.approx(0.5)


def test_empty_predictions_score_zero_without_raising():
    scores = retrieval_scores([], [truth(10.0, 50.0)], k=3)

    assert (scores.precision, scores.recall, scores.f1) == (0.0, 0.0, 0.0)


def test_no_annotations_scores_zero_without_dividing_by_zero():
    scores = retrieval_scores([(10.0, 50.0)], [], k=3)

    assert scores.recall == 0.0
    assert scores.annotated == 0


# ----------------------------------------------------------------------
# GroundTruthSpan validation
# ----------------------------------------------------------------------
def test_a_span_must_end_after_it_starts():
    with pytest.raises(ValueError, match="must end after"):
        GroundTruthSpan(start=50.0, end=50.0)


def test_strength_is_bounded():
    with pytest.raises(ValueError, match="strength"):
        GroundTruthSpan(start=0.0, end=10.0, strength=4)
