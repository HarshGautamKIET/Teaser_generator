"""Validation of AI output and the ranking/selection strategy."""

import pytest

from app.ai.base import RawCandidate, RawCandidateList, RawScores
from app.services.analysis_service import (
    Candidate,
    NoValidCandidatesError,
    clean_text,
    validate_candidates,
)
from app.services.ranking_service import (
    SCORE_WEIGHTS,
    compute_score,
    rank_candidates,
    select_top,
)

VIDEO_DURATION = 100.0


def raw(start, end, title="A moment", hook="A hook", reason="Because", **scores):
    defaults = dict(
        hook=8.0, audience_relevance=8.0, information_value=8.0,
        engagement=8.0, self_contained=8.0,
    )
    defaults.update(scores)
    return RawCandidate(
        start_seconds=start, end_seconds=end, title=title, hook=hook,
        reason=reason, scores=RawScores(**defaults),
    )


def candidate(start, end, score_value=8.0):
    return Candidate(
        start_seconds=start, end_seconds=end, title="t", hook="h", reason="r",
        scores={name: score_value for name in SCORE_WEIGHTS},
    )


# ----------------------------------------------------------------------
# Validation (FR-009)
# ----------------------------------------------------------------------
def test_valid_candidate_is_kept(settings):
    result = validate_candidates(
        RawCandidateList(candidates=[raw(10, 13)]), settings, VIDEO_DURATION
    )

    assert len(result) == 1
    assert result[0].duration_seconds == 3.0


@pytest.mark.parametrize(
    "start,end,why",
    [
        (-5.0, 10.0, "negative start"),
        (50.0, 50.0, "zero length"),
        (50.0, 40.0, "end before start"),
        (95.0, 120.0, "past the end of the video"),
        (10.0, 11.0, "shorter than the minimum"),
        (10.0, 90.0, "longer than the maximum"),
    ],
)
def test_invalid_timestamps_are_discarded(settings, start, end, why):
    with pytest.raises(NoValidCandidatesError):
        validate_candidates(
            RawCandidateList(candidates=[raw(start, end)]), settings, VIDEO_DURATION
        )


def test_valid_candidates_survive_alongside_invalid_ones(settings):
    result = validate_candidates(
        RawCandidateList(
            candidates=[raw(10, 13), raw(200, 260), raw(20, 24), raw(-1, 5)]
        ),
        settings,
        VIDEO_DURATION,
    )

    assert [(c.start_seconds, c.end_seconds) for c in result] == [(10, 13), (20, 24)]


def test_no_candidates_at_all_is_an_error(settings):
    with pytest.raises(NoValidCandidatesError, match="did not return any moments"):
        validate_candidates(RawCandidateList(candidates=[]), settings, VIDEO_DURATION)


# ----------------------------------------------------------------------
# Untrusted string handling (SECURITY.md)
# ----------------------------------------------------------------------
def test_control_characters_are_stripped():
    assert clean_text("Hello\x00\x07 world\n\nagain", 100) == "Hello world again"


def test_long_strings_are_truncated_not_rejected():
    cleaned = clean_text("x" * 500, 50)

    assert len(cleaned) == 50
    assert cleaned.endswith("…")


def test_overlong_ai_text_is_trimmed_rather_than_dropped(settings):
    result = validate_candidates(
        RawCandidateList(candidates=[raw(10, 13, reason="y" * 5000)]),
        settings,
        VIDEO_DURATION,
    )

    assert len(result) == 1
    assert len(result[0].reason) <= 500


def test_whitespace_only_title_is_discarded(settings):
    with pytest.raises(NoValidCandidatesError):
        validate_candidates(
            RawCandidateList(candidates=[raw(10, 13, title="   ")]),
            settings,
            VIDEO_DURATION,
        )


# ----------------------------------------------------------------------
# Scoring (FR-010)
# ----------------------------------------------------------------------
def test_weights_sum_to_one():
    assert sum(SCORE_WEIGHTS.values()) == pytest.approx(1.0)


def test_perfect_scores_give_ten():
    assert compute_score({name: 10.0 for name in SCORE_WEIGHTS}) == 10.0


def test_score_matches_the_documented_weighting():
    scores = {
        "hook": 10.0, "audience_relevance": 0.0, "information_value": 0.0,
        "engagement": 0.0, "self_contained": 0.0,
    }
    # Hook alone carries 30% of the total.
    assert compute_score(scores) == pytest.approx(3.0)


def test_missing_dimension_contributes_nothing():
    assert compute_score({"hook": 10.0}) == pytest.approx(3.0)


def test_ranking_orders_best_first():
    low, high, mid = candidate(0, 3, 4.0), candidate(10, 13, 9.0), candidate(20, 23, 7.0)

    ranked = rank_candidates([low, high, mid])

    assert [c.start_seconds for c in ranked] == [10, 20, 0]


def test_ties_break_toward_the_earlier_moment():
    later, earlier = candidate(50, 53, 8.0), candidate(10, 13, 8.0)

    ranked = rank_candidates([later, earlier])

    assert [c.start_seconds for c in ranked] == [10, 50]


# ----------------------------------------------------------------------
# Selection
# ----------------------------------------------------------------------
def test_select_top_returns_the_requested_number():
    pool = [candidate(i * 10, i * 10 + 3, 9.0 - i) for i in range(6)]

    assert len(select_top(pool, 3)) == 3


def test_selection_skips_overlapping_moments():
    best = candidate(10, 40, 9.5)
    overlapping = candidate(30, 60, 9.0)   # overlaps `best`
    clear = candidate(70, 90, 8.0)

    selected = select_top([best, overlapping, clear], 2)

    assert [c.start_seconds for c in selected] == [10, 70]


def test_selection_returns_fewer_when_everything_overlaps():
    pool = [candidate(10, 40, 9.0), candidate(11, 41, 8.0), candidate(12, 42, 7.0)]

    assert len(select_top(pool, 3)) == 1


def test_touching_clips_are_not_treated_as_overlapping():
    first, second = candidate(10, 40, 9.0), candidate(40, 70, 8.0)

    assert len(select_top([first, second], 2)) == 2


def test_zero_requested_returns_nothing():
    assert select_top([candidate(0, 3)], 0) == []
