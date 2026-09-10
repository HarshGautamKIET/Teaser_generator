"""What a run records about what it discarded.

The pipeline already made every one of these decisions correctly. What it did
not do was count them, which made a run that proposed eight moments and kept one
indistinguishable from a run that kept all eight. These tests pin the counting,
not the decisions -- each of those has its own test elsewhere.
"""

import pytest

from app.ai.base import RawCandidate, RawCandidateList, RawScores
from app.media import Silence
from app.services.analysis_service import (
    NoSelfContainedMomentsError,
    NoValidCandidatesError,
    validate_candidates,
)
from app.services.media_service import snap_window
from app.services.pipeline_report import (
    CandidateReport,
    CutQuality,
    DropReason,
    PipelineReport,
    SnapReport,
)
from app.services.ranking_service import select_top
from tests.test_ranking import candidate

VIDEO_DURATION = 100.0


def raw(start, end, title="A moment", self_contained=9.0):
    return RawCandidate(
        start_seconds=start, end_seconds=end, title=title,
        hook="A hook", reason="Because",
        scores=RawScores(
            hook=8.0, audience_relevance=8.0, information_value=8.0,
            engagement=8.0, self_contained=self_contained,
        ),
    )


# ----------------------------------------------------------------------
# CandidateReport arithmetic
# ----------------------------------------------------------------------
def test_kept_is_derived_from_the_tally():
    """A stored `kept` could disagree with `proposed` minus `dropped`. This
    number is quoted, so it has to be a consequence of the data."""
    report = CandidateReport(proposed=8)
    for _ in range(3):
        report.drop(DropReason.BOUNDS)

    assert report.kept == 5
    assert report.drop_rate == pytest.approx(3 / 8)


def test_an_empty_report_does_not_divide_by_zero():
    assert CandidateReport().drop_rate == 0.0


def test_dropped_counts_are_sorted_in_the_payload():
    """Stable key order, so two identical runs produce byte-identical JSON."""
    report = CandidateReport(proposed=3)
    report.drop(DropReason.TOO_SHORT)
    report.drop(DropReason.BOUNDS)

    assert list(report.to_dict()["dropped"]) == sorted(
        [DropReason.BOUNDS, DropReason.TOO_SHORT]
    )


# ----------------------------------------------------------------------
# Validation counts what it drops
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "start,end,reason",
    [
        (-5.0, 10.0, DropReason.BOUNDS),
        (50.0, 40.0, DropReason.BOUNDS),
        (95.0, 120.0, DropReason.BOUNDS),
        (10.0, 11.0, DropReason.TOO_SHORT),
        (10.0, 90.0, DropReason.TOO_LONG),
    ],
)
def test_each_rejection_is_counted_under_its_own_reason(settings, start, end, reason):
    report = CandidateReport()
    validate_candidates(
        RawCandidateList(candidates=[raw(start, end), raw(20, 23)]),
        settings, VIDEO_DURATION, report=report,
    )

    assert report.dropped == {reason: 1}
    assert report.proposed == 2


def test_empty_text_is_counted(settings):
    report = CandidateReport()
    validate_candidates(
        RawCandidateList(candidates=[raw(10, 13, title="  "), raw(20, 23)]),
        settings, VIDEO_DURATION, report=report,
    )

    assert report.dropped == {DropReason.EMPTY_TEXT: 1}


def test_a_candidate_is_counted_once_under_its_first_failure(settings):
    """Out of bounds *and* too short is one drop, not two. Counting both would
    make the per-reason totals uninterpretable."""
    report = CandidateReport()
    validate_candidates(
        RawCandidateList(candidates=[raw(-5.0, -4.0), raw(20, 23)]),
        settings, VIDEO_DURATION, report=report,
    )

    assert sum(report.dropped.values()) == 1


def test_fragments_are_counted_separately_from_invalid_candidates(settings):
    report = CandidateReport()
    validate_candidates(
        RawCandidateList(
            candidates=[raw(10, 13, self_contained=1.0), raw(20, 23)]
        ),
        settings, VIDEO_DURATION, min_self_contained=7.0, report=report,
    )

    assert report.dropped == {DropReason.NOT_SELF_CONTAINED: 1}


def test_a_run_that_fails_still_records_what_it_dropped(settings):
    """The tally of a failed run is the interesting one: "eight proposed, eight
    out of bounds" is the whole diagnosis."""
    report = CandidateReport()
    with pytest.raises(NoValidCandidatesError):
        validate_candidates(
            RawCandidateList(candidates=[raw(-5.0, 10.0), raw(200.0, 260.0)]),
            settings, VIDEO_DURATION, report=report,
        )

    assert report.proposed == 2
    assert report.dropped == {DropReason.BOUNDS: 2}


def test_a_run_that_fails_on_self_containment_records_that_too(settings):
    report = CandidateReport()
    with pytest.raises(NoSelfContainedMomentsError):
        validate_candidates(
            RawCandidateList(candidates=[raw(10, 13, self_contained=1.0)]),
            settings, VIDEO_DURATION, min_self_contained=7.0, report=report,
        )

    assert report.dropped == {DropReason.NOT_SELF_CONTAINED: 1}


def test_validation_without_a_report_still_works(settings):
    """The out parameter is optional; every existing caller passes nothing."""
    assert len(validate_candidates(
        RawCandidateList(candidates=[raw(10, 13)]), settings, VIDEO_DURATION
    )) == 1


# ----------------------------------------------------------------------
# Selection counts what it passes over
# ----------------------------------------------------------------------
def test_outranked_candidates_are_counted():
    report = CandidateReport(proposed=5)
    select_top([candidate(i * 10.0, i * 10.0 + 5.0) for i in range(5)], 2, report=report)

    assert report.dropped == {DropReason.OUTRANKED: 3}


def test_candidates_inside_the_gap_are_counted_separately():
    """Losing on rank and losing on spacing are different answers to "why did I
    only get one clip", so they are counted apart."""
    report = CandidateReport(proposed=2)
    selected = select_top(
        [candidate(0.0, 5.0, 9.0), candidate(6.0, 11.0, 8.0)],
        2, min_gap_seconds=30.0, report=report,
    )

    assert len(selected) == 1
    assert report.dropped == {DropReason.TOO_CLOSE: 1}


def test_the_tail_the_loop_never_reached_is_still_counted():
    """select_top breaks once the quota is full, so counting inside the loop
    would undercount by exactly the part being measured."""
    report = CandidateReport(proposed=10)
    select_top([candidate(i * 10.0, i * 10.0 + 5.0) for i in range(10)], 1, report=report)

    assert report.dropped[DropReason.OUTRANKED] == 9


def test_a_report_reused_across_calls_counts_each_call():
    report = CandidateReport(proposed=6)
    pool = [candidate(i * 10.0, i * 10.0 + 5.0) for i in range(3)]

    select_top(pool, 1, report=report)
    select_top(pool, 1, report=report)

    assert report.dropped[DropReason.OUTRANKED] == 4


# ----------------------------------------------------------------------
# Snapping counts whether it did anything
# ----------------------------------------------------------------------
def test_a_boundary_that_moves_is_counted_as_moved(settings):
    report = SnapReport()
    snap_window(
        10.0, 14.0, [Silence(9.0, 10.4), Silence(13.6, 15.0)],
        settings, 100.0, report=report,
    )

    assert (report.starts_moved, report.ends_moved) == (1, 1)
    assert report.move_rate == 1.0


def test_a_boundary_with_no_pause_nearby_is_counted_as_kept(settings):
    report = SnapReport()
    snap_window(50.0, 54.0, [Silence(0.0, 1.0)], settings, 100.0, report=report)

    assert (report.starts_moved, report.ends_moved) == (0, 0)
    assert (report.starts_kept, report.ends_kept) == (1, 1)
    assert report.move_rate == 0.0


def test_no_silences_at_all_is_not_counted_as_declining(settings):
    """Snapping that never ran must not be reported as snapping that failed."""
    report = SnapReport()
    snap_window(10.0, 14.0, [], settings, 100.0, report=report)

    assert report.considered == 0
    assert report.move_rate == 0.0


def test_a_rejected_snap_counts_both_ends_as_kept(settings):
    """When the snapped window breaks the length limits the unsnapped one ships,
    so crediting a move that was discarded would overstate the feature."""
    report = SnapReport()
    # settings.teaser_max_seconds is 5 in the test config; snapping both ends
    # outward would make the clip longer than that, so the move is refused.
    start, end = snap_window(
        10.0, 14.0, [Silence(6.0, 8.5), Silence(16.0, 18.0)],
        settings, 100.0, report=report,
    )

    assert (start, end) == (10.0, 14.0)
    assert (report.starts_moved, report.ends_moved) == (0, 0)
    assert (report.starts_kept, report.ends_kept) == (1, 1)


def test_mean_shift_is_absolute(settings):
    """One end moving earlier and one later must not cancel out to zero."""
    report = SnapReport(shifts=[-0.5, 0.5])

    assert report.mean_abs_shift_seconds == pytest.approx(0.5)


# ----------------------------------------------------------------------
# Cut quality
# ----------------------------------------------------------------------
def test_a_quiet_opening_is_a_clean_cut():
    cut = CutQuality("t1", opening_db=-45.0, clip_db=-22.0, threshold_db=-6.0)

    assert cut.delta_db == pytest.approx(-23.0)
    assert cut.clean


def test_an_opening_at_speech_level_is_not_clean():
    """A clip that starts mid-word starts at about the level of the rest of it."""
    cut = CutQuality("t1", opening_db=-21.0, clip_db=-22.0, threshold_db=-6.0)

    assert not cut.clean


def test_cut_quality_is_relative_to_the_clip_not_absolute():
    """A quietly-recorded talk must not score as all-clean, nor a loud one as
    all-broken -- an absolute floor would measure gain, not the cut."""
    quiet = CutQuality("t1", opening_db=-60.0, clip_db=-58.0, threshold_db=-6.0)
    loud = CutQuality("t2", opening_db=-20.0, clip_db=-4.0, threshold_db=-6.0)

    assert not quiet.clean
    assert loud.clean


# ----------------------------------------------------------------------
# The whole report
# ----------------------------------------------------------------------
def test_degrade_is_idempotent():
    report = PipelineReport()
    report.degrade("no_summary")
    report.degrade("no_summary")

    assert report.degraded == ["no_summary"]


def test_clean_cut_rate_over_no_measurements_is_zero():
    assert PipelineReport().clean_cut_rate == 0.0


def test_the_payload_is_json_serialisable():
    import json

    report = PipelineReport()
    report.candidates.proposed = 4
    report.candidates.drop(DropReason.BOUNDS)
    report.snap.starts_moved = 1
    report.cuts.append(CutQuality("t1", -40.0, -20.0, -6.0))
    report.degrade("no_summary")

    payload = json.loads(json.dumps(report.to_dict()))

    assert payload["candidates"]["kept"] == 3
    assert payload["clean_cut_rate"] == 1.0
    assert payload["degraded"] == ["no_summary"]
