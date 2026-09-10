"""One component disabled per row.

The property this module has to get right is not any particular delta -- those
depend on the asset -- but that it never reports a number it did not measure. A
delta of zero reads as "this component does not matter", which is the opposite
claim from "we could not test it", and confusing the two is how a component
gets deleted for looking useless.
"""

import pytest

from app.evaluation.ablation import ABLATIONS, AblationRow, deltas, run
from app.evaluation.harness import GroundTruth
from app.evaluation.metrics import GroundTruthSpan
from app.services.analysis_service import Candidate
from app.services.ranking_service import SCORE_WEIGHTS

DURATION = 1000.0


def candidate(start, end, hook=8.0, self_contained=8.0):
    return Candidate(
        start_seconds=start, end_seconds=end,
        title=f"Moment at {start}", hook="h", reason="r",
        scores={
            "hook": hook,
            "audience_relevance": 8.0,
            "information_value": 8.0,
            "engagement": 8.0,
            "self_contained": self_contained,
        },
    )


def truth(*spans):
    return GroundTruth(
        asset_id="test",
        duration_seconds=DURATION,
        spans=[GroundTruthSpan(start=s, end=e) for s, e in spans],
    )


# ----------------------------------------------------------------------
# Rows that cannot be measured say so
# ----------------------------------------------------------------------
def test_unmeasurable_rows_are_reported_as_unavailable():
    """Anything upstream of selection needs a fresh analysis to ablate. Those
    rows must not report a delta of zero."""
    rows = run([candidate(0.0, 40.0)], truth((0.0, 40.0)), 3, 0.0, 5.0)
    by_name = {row.name: row for row in rows}

    for ablation in ABLATIONS:
        if ablation.needs is not None:
            assert not by_name[ablation.name].available
            assert by_name[ablation.name].unavailable_reason


def test_every_declared_ablation_appears_in_the_output():
    """A row that silently vanished would read as one that passed."""
    rows = run([candidate(0.0, 40.0)], truth((0.0, 40.0)), 3, 0.0, 5.0)

    assert {row.name for row in rows} == {a.name for a in ABLATIONS}


def test_unavailable_rows_are_excluded_from_the_deltas():
    rows = run([candidate(0.0, 40.0)], truth((0.0, 40.0)), 3, 0.0, 5.0)
    result = deltas(rows, 3)

    for name, row in result["rows"].items():
        if not row["available"]:
            assert "delta" not in row
            assert row["reason"]


# ----------------------------------------------------------------------
# The components that can be measured
# ----------------------------------------------------------------------
def test_the_self_contained_floor_row_differs_from_the_control():
    """The control drops the fragment; the ablation keeps it, and it wins on
    hook. If both rows selected the same thing the floor would be untested."""
    candidates = [
        candidate(0.0, 40.0, hook=10.0, self_contained=1.0),   # fragment
        candidate(500.0, 540.0, hook=6.0, self_contained=9.0),  # stands alone
    ]
    rows = {r.name: r for r in run(candidates, truth((500.0, 540.0)), 1, 0.0, 5.0)}

    assert rows["none"].selected == [(500.0, 540.0)]
    assert rows["self_contained_floor"].selected == [(0.0, 40.0)]


def test_removing_the_floor_scores_worse_when_the_fragment_is_wrong():
    candidates = [
        candidate(0.0, 40.0, hook=10.0, self_contained=1.0),
        candidate(500.0, 540.0, hook=6.0, self_contained=9.0),
    ]
    rows = run(candidates, truth((500.0, 540.0)), 1, 0.0, 5.0)
    result = deltas(rows, 1)

    # Negative: the pipeline is better with the floor than without it.
    assert result["rows"]["self_contained_floor"]["delta"] < 0


def test_the_min_gap_row_allows_adjacent_moments():
    candidates = [
        candidate(0.0, 40.0, hook=9.0),
        candidate(45.0, 85.0, hook=8.0),
    ]
    rows = {r.name: r for r in run(candidates, truth((0.0, 40.0)), 2, 100.0, 5.0)}

    assert len(rows["none"].selected) == 1
    assert len(rows["min_gap"].selected) == 2


def test_the_ranking_row_takes_model_order():
    """Model order, gap rule still applied: this ablates the ranking, not the
    separation rule, so a difference points at one of them rather than both."""
    candidates = [
        candidate(0.0, 40.0, hook=1.0),     # first, but worst
        candidate(500.0, 540.0, hook=10.0),  # best
    ]
    rows = {r.name: r for r in run(candidates, truth((0.0, 40.0)), 1, 0.0, 5.0)}

    assert rows["none"].selected == [(500.0, 540.0)]
    assert rows["ranking"].selected == [(0.0, 40.0)]


def test_the_weights_row_does_not_contaminate_the_control():
    """rank_candidates writes Candidate.score in place, so ablating the weights
    on the shared objects would leave every later row scoring against the
    ablated values."""
    candidates = [candidate(0.0, 40.0, hook=10.0), candidate(500.0, 540.0, hook=2.0)]
    rows = run(candidates, truth((0.0, 40.0)), 1, 0.0, 5.0)
    control = next(r for r in rows if r.name == "none")

    # Hook carries the heaviest weight, so the control still prefers the first.
    assert control.selected == [(0.0, 40.0)]
    # And the original objects still carry their original dimension values.
    assert candidates[0].scores["hook"] == 10.0


def test_uniform_weights_change_the_order_when_hook_was_carrying_it():
    """Under the shipped weights hook is worth 30%; under a flat mean it is
    worth 20%, so a candidate that led only on hook can lose."""
    candidates = [
        candidate(0.0, 40.0, hook=10.0, self_contained=6.0),
        candidate(500.0, 540.0, hook=7.0, self_contained=10.0),
    ]
    rows = {r.name: r for r in run(candidates, truth((0.0, 40.0)), 1, 0.0, 5.0)}

    assert rows["none"].selected != rows["score_weights"].selected


# ----------------------------------------------------------------------
# deltas
# ----------------------------------------------------------------------
def test_deltas_are_measured_against_the_control():
    rows = run([candidate(0.0, 40.0)], truth((0.0, 40.0)), 1, 0.0, 5.0)
    result = deltas(rows, 1)

    assert result["control"] == 1.0
    assert "none" not in result["rows"]


def test_deltas_without_a_control_report_nothing():
    """Rather than picking an arbitrary row to compare against."""
    assert deltas([AblationRow(name="min_gap", description="x")], 3)["control"] is None


def test_weights_still_sum_to_one():
    """The ablation reasons about these; a change to them should surface here
    as well as in ranking_service's own assertion."""
    assert sum(SCORE_WEIGHTS.values()) == pytest.approx(1.0)
