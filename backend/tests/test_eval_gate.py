"""The CI regression gate.

This is what turns evaluation from a report somebody reads once into a thing
that stops a worse prompt shipping, so its failure modes matter more than its
success. Three of them in particular:

* an empty corpus must not pass -- every threshold is trivially satisfied when
  there is nothing to score;
* an asset with annotations and no run must score zero rather than being
  skipped, or a change that stops producing output raises the average;
* a baseline that could not be computed must fail the check that names it,
  rather than being treated as beaten.

The gate reads only committed files, so everything here runs with no database,
no media, no FFmpeg and no API key.
"""

import json

import pytest

from app.evaluation.cli import GATE_K, _check, cmd_gate, load_fixtures, main
from app.evaluation.harness import score, summarise


class Args:
    def __init__(self, directory):
        self.dir = str(directory)


def write(root, asset_id, spans, run_spans=None, duration=1000.0):
    (root / "ground_truth").mkdir(parents=True, exist_ok=True)
    (root / "runs").mkdir(parents=True, exist_ok=True)

    (root / "ground_truth" / f"{asset_id}.json").write_text(
        json.dumps({
            "asset_id": asset_id,
            "duration_seconds": duration,
            "spans": [{"start": s, "end": e} for s, e in spans],
        }),
        encoding="utf-8",
    )
    if run_spans is not None:
        (root / "runs" / f"{asset_id}.json").write_text(
            json.dumps({
                "asset_id": asset_id,
                "spans": [{"start": s, "end": e} for s, e in run_spans],
            }),
            encoding="utf-8",
        )


def thresholds(root, payload):
    (root / "thresholds.json").write_text(json.dumps(payload), encoding="utf-8")


# ----------------------------------------------------------------------
# The committed corpus
# ----------------------------------------------------------------------
def test_the_repository_fixtures_pass_the_gate(capsys):
    """The gate committed to this repository is green. If it is not, either the
    fixtures or the selection rules changed and somebody has to look."""
    assert main(["gate"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"]
    assert payload["failures"] == []


def test_the_repository_fixtures_beat_every_named_baseline(capsys):
    """The claim the whole package exists to support."""
    main(["gate"])
    summary = json.loads(capsys.readouterr().out)["summary"]

    for name, baseline in summary["baselines"].items():
        assert summary["pipeline"]["precision"] > baseline["precision"], name


def test_the_committed_corpus_has_more_than_one_asset():
    """A one-row average moves entirely with that row."""
    from app.config import get_settings

    assert len(load_fixtures(get_settings().evaluation_path)) >= 2


# ----------------------------------------------------------------------
# Failure modes
# ----------------------------------------------------------------------
def test_an_empty_corpus_fails_rather_than_passing_vacuously(tmp_path, capsys):
    """A gate that goes green when its own inputs vanish is worse than no gate."""
    assert cmd_gate(Args(tmp_path)) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "no fixtures"


def test_an_asset_with_no_recorded_run_scores_zero(tmp_path, capsys):
    """Not skipped. Skipping would let a change that stops producing output for
    one asset raise the corpus average."""
    write(tmp_path, "annotated-only", [(100.0, 140.0)], run_spans=None)
    thresholds(tmp_path, {"min_precision": 0.5})

    assert cmd_gate(Args(tmp_path)) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["assets"][0]["missing_run"] is True
    assert payload["summary"]["pipeline"]["precision"] == 0.0


def test_a_regression_below_the_floor_fails_the_build(tmp_path, capsys):
    write(tmp_path, "asset", [(100.0, 140.0), (500.0, 540.0)], [(800.0, 840.0)])
    thresholds(tmp_path, {"min_precision": 0.5})

    assert cmd_gate(Args(tmp_path)) == 1
    assert "below the 0.5 floor" in json.loads(capsys.readouterr().out)["failures"][0]


def test_scoring_at_or_above_the_floor_passes(tmp_path, capsys):
    write(
        tmp_path, "asset",
        [(100.0, 140.0), (500.0, 540.0), (800.0, 840.0)],
        [(100.0, 140.0), (500.0, 540.0), (800.0, 840.0)],
    )
    thresholds(tmp_path, {"min_precision": 0.9})

    assert cmd_gate(Args(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out)["passed"]


def test_a_corpus_with_no_thresholds_file_still_reports(tmp_path, capsys):
    """No thresholds means nothing to fail, but the numbers are still emitted --
    which is how a new corpus is bootstrapped before its floor is chosen."""
    write(tmp_path, "asset", [(100.0, 140.0)], [(100.0, 140.0)])

    assert cmd_gate(Args(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["assets"] == 1


# ----------------------------------------------------------------------
# _check
# ----------------------------------------------------------------------
def test_a_baseline_that_was_not_computed_fails_the_check():
    """Never treated as beaten. A baseline that silently did not run reads as
    one the pipeline won against."""
    summary = {
        "k": 3,
        "pipeline": {"precision": 0.9},
        "baselines": {"uniform": {"precision": 0.1}},
    }

    failures = _check(summary, {"beat_baselines": ["uniform", "audio_peak"]})

    assert len(failures) == 1
    assert "audio_peak" in failures[0]
    assert "cannot check" in failures[0]


def test_merely_tying_a_baseline_is_not_beating_it():
    summary = {
        "k": 3,
        "pipeline": {"precision": 0.4},
        "baselines": {"uniform": {"precision": 0.4}},
    }

    assert _check(summary, {"beat_baselines": ["uniform"]})


def test_a_summary_with_no_assets_fails():
    assert _check({"k": 3, "pipeline": None}, {}) == ["no assets were scored"]


def test_no_thresholds_means_no_failures():
    summary = {"k": 3, "pipeline": {"precision": 0.0}, "baselines": {}}

    assert _check(summary, {}) == []


# ----------------------------------------------------------------------
# Honest reporting of what could not be run
# ----------------------------------------------------------------------
def test_baselines_needing_media_are_named_as_unavailable(tmp_path):
    """Rather than omitted. An absent row reads as "the pipeline beat every
    baseline"; a named one reads as "we did not measure this"."""
    write(tmp_path, "asset", [(100.0, 140.0)], [(100.0, 140.0)])
    truth, spans = load_fixtures(tmp_path)[0]

    result = score(spans, truth, (GATE_K,), source=None, captions=None)

    assert "audio_peak" in result.unavailable
    assert "keyword" in result.unavailable
    assert result.unavailable["audio_peak"]


def test_the_summary_states_how_many_assets_each_baseline_covered(tmp_path):
    """A baseline computed on one asset out of five is not comparable with one
    computed on all five, and the average alone would not show it."""
    write(tmp_path, "a", [(100.0, 140.0)], [(100.0, 140.0)])
    write(tmp_path, "b", [(100.0, 140.0)], [(100.0, 140.0)])
    results = [
        score(spans, truth, (GATE_K,)) for truth, spans in load_fixtures(tmp_path)
    ]

    summary = summarise(results, GATE_K)

    assert summary["baselines"]["uniform"]["assets"] == 2
