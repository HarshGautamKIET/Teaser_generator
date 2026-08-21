"""Every teaser has to stand completely alone.

Self-containment used to be a 10% weight in the ranking score, which is not the
same thing as a requirement: hook carries three times that, so a fragment with a
strong opening still won. These tests pin down the difference between "ranked
lower" and "not eligible".

The second half covers separation. Two clips that never overlap can still be one
continuous passage cut in half, which fails the same requirement for a reason
scoring cannot see.
"""

import pytest

from app.ai.base import RawCandidate, RawCandidateList
from app.config import get_settings
from app.services.analysis_service import (
    Candidate,
    NoSelfContainedMomentsError,
    validate_candidates,
)
from app.services.ranking_service import (
    affordable_gap,
    select_top,
    separation_seconds,
)
from tests.conftest import requires_ffmpeg
from tests.test_generation import StubProvider, run, scores


def raw(start, end, self_contained=9.0, hook=8.0):
    """One candidate with self_contained set independently of the rest."""
    from app.ai.base import RawScores

    return RawCandidate(
        start_seconds=start, end_seconds=end,
        title="A moment", hook="Worth watching.", reason="For the test.",
        scores=RawScores(
            hook=hook, audience_relevance=8.0, information_value=8.0,
            engagement=8.0, self_contained=self_contained,
        ),
    )


def candidate(start, end, score=8.0):
    return Candidate(
        start_seconds=start, end_seconds=end,
        title="A moment", hook="Worth watching.", reason="For the test.",
        scores={
            "hook": score, "audience_relevance": score,
            "information_value": score, "engagement": score,
            "self_contained": score,
        },
    )


# ----------------------------------------------------------------------
# The floor
# ----------------------------------------------------------------------
def test_fragments_are_discarded_not_merely_ranked_lower():
    settings = get_settings()
    raw_list = RawCandidateList(
        candidates=[
            raw(0, 3, self_contained=2.0, hook=10.0),   # brilliant hook, fragment
            raw(10, 13, self_contained=9.0, hook=5.0),  # dull hook, complete
        ]
    )

    kept = validate_candidates(
        raw_list, settings, video_duration=60.0, min_self_contained=7.0
    )

    assert len(kept) == 1
    assert kept[0].start_seconds == 10.0


def test_the_old_weighting_would_have_kept_the_fragment():
    """Shows the gap this closes: on score alone, the fragment wins."""
    from app.services.ranking_service import compute_score

    fragment = candidate(0, 3).scores | {"self_contained": 2.0, "hook": 10.0}
    complete = candidate(10, 13).scores | {"self_contained": 9.0, "hook": 5.0}

    assert compute_score(fragment) > compute_score(complete)


def test_a_run_where_nothing_stands_alone_fails_honestly():
    settings = get_settings()
    raw_list = RawCandidateList(
        candidates=[raw(0, 3, self_contained=3.0), raw(10, 13, self_contained=4.0)]
    )

    with pytest.raises(NoSelfContainedMomentsError) as caught:
        validate_candidates(
            raw_list, settings, video_duration=60.0, min_self_contained=7.0
        )

    assert caught.value.code == "NO_SELF_CONTAINED_MOMENTS"
    # Distinct from "found nothing at all", so the advice can differ.
    assert "none of them stood on their own" in caught.value.message


def test_a_moment_exactly_on_the_threshold_is_kept():
    settings = get_settings()
    raw_list = RawCandidateList(candidates=[raw(0, 3, self_contained=7.0)])

    kept = validate_candidates(
        raw_list, settings, video_duration=60.0, min_self_contained=7.0
    )

    assert len(kept) == 1


def test_a_zero_threshold_disables_the_filter():
    settings = get_settings()
    raw_list = RawCandidateList(candidates=[raw(0, 3, self_contained=0.0)])

    kept = validate_candidates(
        raw_list, settings, video_duration=60.0, min_self_contained=0.0
    )

    assert len(kept) == 1


def test_the_server_default_is_used_when_none_is_given():
    settings = get_settings()
    below = settings.teaser_min_self_contained - 1
    raw_list = RawCandidateList(candidates=[raw(0, 3, self_contained=below)])

    with pytest.raises(NoSelfContainedMomentsError):
        validate_candidates(raw_list, settings, video_duration=60.0)


# ----------------------------------------------------------------------
# Separation
# ----------------------------------------------------------------------
def test_separation_is_negative_for_overlapping_moments():
    assert separation_seconds(candidate(0, 30), candidate(20, 50)) < 0


def test_separation_is_zero_for_adjacent_moments():
    assert separation_seconds(candidate(0, 30), candidate(30, 60)) == 0


def test_separation_is_measured_in_either_direction():
    assert separation_seconds(candidate(45, 60), candidate(0, 30)) == 15


def test_adjacent_moments_are_rejected_when_a_gap_is_required():
    """The case non-overlap alone allows: clip 2 starts where clip 1 stopped."""
    chosen = select_top(
        [candidate(0, 30, score=9.0), candidate(30, 60, score=8.0)],
        count=2,
        min_gap_seconds=15,
    )

    assert len(chosen) == 1
    assert chosen[0].start_seconds == 0


def test_separated_moments_are_both_kept():
    chosen = select_top(
        [candidate(0, 30, score=9.0), candidate(45, 75, score=8.0)],
        count=2,
        min_gap_seconds=15,
    )

    assert len(chosen) == 2


def test_a_zero_gap_reduces_to_the_previous_non_overlap_behaviour():
    adjacent = select_top(
        [candidate(0, 30, score=9.0), candidate(30, 60, score=8.0)],
        count=2, min_gap_seconds=0,
    )
    overlapping = select_top(
        [candidate(0, 30, score=9.0), candidate(20, 50, score=8.0)],
        count=2, min_gap_seconds=0,
    )

    assert len(adjacent) == 2, "adjacent clips were allowed before"
    assert len(overlapping) == 1, "overlapping clips never were"


def test_the_gap_is_measured_against_every_chosen_moment():
    """Not just the previous one: a later candidate can sit between two."""
    chosen = select_top(
        [
            candidate(0, 20, score=9.0),
            candidate(60, 80, score=8.0),
            candidate(30, 50, score=7.0),   # 10s from the first, 10s from the second
        ],
        count=3,
        min_gap_seconds=15,
    )

    assert len(chosen) == 2
    assert [c.start_seconds for c in chosen] == [0, 60]


def test_a_lower_scoring_but_separated_moment_beats_a_crowded_one():
    chosen = select_top(
        [
            candidate(0, 20, score=9.0),
            candidate(25, 45, score=8.5),   # only 5s away
            candidate(90, 110, score=6.0),  # far, but weaker
        ],
        count=2,
        min_gap_seconds=15,
    )

    assert [c.start_seconds for c in chosen] == [0, 90]


# ----------------------------------------------------------------------
# The gap is a preference, bounded by what the video can spare
# ----------------------------------------------------------------------
def test_a_long_video_gets_the_configured_gap():
    """Forty minutes has room to spare, so nothing is reduced."""
    assert affordable_gap(15, video_duration=2400, count=3, min_clip_seconds=20) == 15


def test_a_short_video_gets_a_reduced_gap():
    """81s, 3 clips of >=20s: 21s spare across 2 gaps, so 10.5s each.

    The real case this was written for -- a fixed 15s gap needs 105s of video
    for this run and silently returns one clip instead of three.
    """
    assert affordable_gap(15, video_duration=81, count=3, min_clip_seconds=20) == 10.5


def test_a_video_with_nothing_to_spare_falls_back_to_non_overlap():
    assert affordable_gap(15, video_duration=60, count=3, min_clip_seconds=20) == 0


def test_an_over_subscribed_video_falls_back_rather_than_going_negative():
    assert affordable_gap(15, video_duration=30, count=3, min_clip_seconds=20) == 0


def test_a_single_clip_needs_no_gap():
    assert affordable_gap(15, video_duration=600, count=1, min_clip_seconds=20) == 0


def test_a_disabled_gap_stays_disabled():
    assert affordable_gap(0, video_duration=600, count=3, min_clip_seconds=20) == 0


# ----------------------------------------------------------------------
# End to end
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_generated_clips_are_separated_in_a_real_run(client, uploaded_video):
    """The 8s fixture with a 2s gap: the pipeline must honour it in the output."""
    video_id = uploaded_video["video_id"]
    job_id = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    job = run(job_id, StubProvider(_spaced_candidates()))
    assert job.status == "completed", job.error_message

    teasers = client.get(
        f"/api/videos/{video_id}/teasers?job_id={job_id}"
    ).json()["teasers"]

    windows = sorted((t["start_seconds"], t["end_seconds"]) for t in teasers)
    gaps = [
        later[0] - earlier[1] for earlier, later in zip(windows, windows[1:])
    ]
    assert all(gap >= 0 for gap in gaps), f"clips are not separated: {windows}"


def _spaced_candidates():
    """Two well-separated moments inside the 8s fixture video."""
    return [
        RawCandidate(
            start_seconds=0.0, end_seconds=2.5, title="Opening",
            hook="A striking claim.", reason="Complete on its own.",
            scores=scores(9.0),
        ),
        RawCandidate(
            start_seconds=5.5, end_seconds=7.9, title="Closing",
            hook="What it means.", reason="Complete on its own.",
            scores=scores(8.0),
        ),
    ]
