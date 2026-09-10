"""Command line entry point for the evaluation harness.

    python -m app.evaluation report --job <job_id>    # what one run discarded
    python -m app.evaluation score  --video <video_id>  # vs annotations + baselines
    python -m app.evaluation ablate --video <video_id>  # one component off per row
    python -m app.evaluation gate                       # the CI regression check

`gate` is the only subcommand that must run anywhere. It scores committed
fixtures -- annotations plus the spans a recorded run produced -- so it needs no
database, no media on disk, no FFmpeg and no API key, and can therefore run on
every pull request. The other three read the live database, because their whole
value is being pointed at real runs.

The gate fails the build when a headline number drops below its recorded
threshold. That is the point of the entire package: without it, a prompt change
that makes the clips worse is indistinguishable from one that makes them better
until somebody watches thirty videos.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.evaluation import ablation, harness
from app.evaluation.metrics import DEFAULT_KS

logger = logging.getLogger(__name__)

#: The gate's headline. Precision at 3 rather than 5, because this product cuts
#: three clips by default: scoring at a K it never returns would measure a
#: configuration nobody runs.
GATE_K = 3

#: Fixtures the gate reads. Committed, small, and deliberately not generated at
#: gate time -- a gate that regenerated its own expectations would pass forever.
GROUND_TRUTH_DIR = "ground_truth"
RUNS_DIR = "runs"
THRESHOLDS_FILE = "thresholds.json"


def _emit(payload: dict[str, Any]) -> None:
    """JSON to stdout. Machine-readable because the gate's output is an artifact."""
    json.dump(payload, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")


# ----------------------------------------------------------------------
# report -- Tier 0, straight off the job row
# ----------------------------------------------------------------------
def cmd_report(args: argparse.Namespace) -> int:
    from app.database import user_session
    from app.services import generation_service

    with user_session(args.user) as db:
        job = generation_service.get_job(db, args.job)
        if job.pipeline_report is None:
            _emit({
                "job_id": job.id,
                "status": job.status,
                "report": None,
                "note": "This run predates the report, or failed before analysis.",
            })
            return 0
        _emit({
            "job_id": job.id,
            "status": job.status,
            "audience": job.audience,
            "recording_type": job.recording_type,
            "report": job.pipeline_report,
        })
    return 0


# ----------------------------------------------------------------------
# score -- Tiers 2 and 3, against the live database
# ----------------------------------------------------------------------
def cmd_score(args: argparse.Namespace) -> int:
    from app.database import user_session
    from app.models import Video
    from app.storage import UPLOADS, get_storage

    settings = get_settings()
    storage = get_storage()

    with user_session(args.user) as db:
        truth = _resolve_truth(db, args.video, settings)
        if truth is None:
            _emit({
                "error": "no ground truth",
                "video_id": args.video,
                "note": (
                    f"Add {settings.evaluation_path / GROUND_TRUTH_DIR}/"
                    f"{args.video}.json, or mark some clips `keep` in the app."
                ),
            })
            return 1

        predictions = harness.predictions_from_db(db, args.video, args.job)
        video = db.get(Video, args.video)
        source = (
            storage.resolve(UPLOADS, video.storage_key)
            if video is not None and not args.no_media
            else None
        )
        result = harness.score(
            predictions, truth, DEFAULT_KS, source, None, settings.ffmpeg_path
        )

    _emit({
        "asset": result.to_dict(),
        "summary": harness.summarise([result], GATE_K),
    })
    return 0


def _resolve_truth(db, video_id: str, settings) -> harness.GroundTruth | None:
    """Annotation file if there is one, otherwise the user's own verdicts.

    File first. A hand-annotated set can contain moments the pipeline missed,
    which is the only way recall means anything; feedback can only ever describe
    clips the pipeline already produced.
    """
    path = settings.evaluation_path / GROUND_TRUTH_DIR / f"{video_id}.json"
    if path.is_file():
        return harness.GroundTruth.from_file(path)
    return harness.ground_truth_from_feedback(db, video_id)


# ----------------------------------------------------------------------
# ablate -- Tier 4
# ----------------------------------------------------------------------
def cmd_ablate(args: argparse.Namespace) -> int:
    from app.database import user_session
    from app.domain import DEFAULT_RECORDING_TYPE, RECORDING_PROFILES, RecordingType
    from app.models import Job, JobStatus, Teaser

    settings = get_settings()

    with user_session(args.user) as db:
        truth = _resolve_truth(db, args.video, settings)
        if truth is None:
            _emit({"error": "no ground truth", "video_id": args.video})
            return 1

        job = (
            db.query(Job)
            .filter(Job.video_id == args.video, Job.status == JobStatus.COMPLETED)
            .order_by(Job.created_at.desc())
            .first()
        )
        if job is None:
            _emit({"error": "no completed run for this video", "video_id": args.video})
            return 1

        # The clips a run produced, reconstituted as candidates. Not the same as
        # everything analysis proposed -- the discarded candidates were never
        # stored -- so the self_contained_floor row here compares "the clips that
        # shipped" against "the clips that shipped", and reports as such.
        rows = (
            db.query(Teaser).filter(Teaser.job_id == job.id).order_by(Teaser.rank).all()
        )
        candidates = [
            _candidate_from_teaser(teaser) for teaser in rows
        ]
        profile = RECORDING_PROFILES[
            RecordingType(job.recording_type or DEFAULT_RECORDING_TYPE)
        ]
        floor = (
            settings.teaser_min_self_contained
            if profile.min_self_contained is None
            else profile.min_self_contained
        )
        gap = (
            settings.teaser_min_gap_seconds
            if profile.min_gap_seconds is None
            else profile.min_gap_seconds
        )
        results = ablation.run(
            candidates,
            truth,
            job.teaser_count or settings.teaser_count,
            gap,
            floor,
        )

    _emit({
        "video_id": args.video,
        "job_id": job.id,
        "note": (
            "Ablated over the clips this run produced. Candidates the pipeline "
            "discarded are not stored, so rows that depend on them understate "
            "the component's effect."
        ),
        "rows": [row.to_dict() for row in results],
        "deltas": ablation.deltas(results, GATE_K),
    })
    return 0


def _candidate_from_teaser(teaser) -> Any:
    from app.services.analysis_service import Candidate

    return Candidate(
        start_seconds=teaser.start_seconds,
        end_seconds=teaser.end_seconds,
        title=teaser.title,
        hook=teaser.hook,
        reason=teaser.reason,
        scores=dict(teaser.scores or {}),
    )


# ----------------------------------------------------------------------
# gate -- Tier 5, the CI check
# ----------------------------------------------------------------------
def load_fixtures(root: Path) -> list[tuple[harness.GroundTruth, list[tuple[float, float]]]]:
    """Committed (annotations, recorded predictions) pairs.

    An asset with annotations but no recorded run is returned with an empty
    prediction list rather than skipped, so it scores zero and drags the average
    down. Skipping it would let a run that stopped producing output for one
    asset raise the corpus average.
    """
    truths = harness.load_ground_truth_dir(root / GROUND_TRUTH_DIR)
    runs_dir = root / RUNS_DIR

    pairs = []
    for truth in truths:
        run_path = runs_dir / f"{truth.asset_id}.json"
        spans: list[tuple[float, float]] = []
        if run_path.is_file():
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            spans = [(float(s["start"]), float(s["end"])) for s in payload["spans"]]
        pairs.append((truth, spans))
    return pairs


def cmd_gate(args: argparse.Namespace) -> int:
    settings = get_settings()
    root = Path(args.dir) if args.dir else settings.evaluation_path

    pairs = load_fixtures(root)
    if not pairs:
        _emit({
            "error": "no fixtures",
            "dir": str(root),
            "note": (
                f"The gate needs at least one annotation in {root / GROUND_TRUTH_DIR}."
            ),
        })
        # Not a pass. An empty corpus satisfies every threshold trivially, and a
        # gate that goes green when its own inputs vanish is worse than no gate.
        return 1

    results = [
        harness.score(spans, truth, DEFAULT_KS, None, None) for truth, spans in pairs
    ]
    summary = harness.summarise(results, GATE_K)

    thresholds_path = root / THRESHOLDS_FILE
    thresholds = (
        json.loads(thresholds_path.read_text(encoding="utf-8"))
        if thresholds_path.is_file()
        else {}
    )

    failures = _check(summary, thresholds)
    _emit({
        "k": GATE_K,
        "assets": [r.to_dict() for r in results],
        "summary": summary,
        "thresholds": thresholds,
        "failures": failures,
        "passed": not failures,
    })
    return 1 if failures else 0


def _check(summary: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    """Every threshold the corpus missed, as sentences.

    Two kinds. `min_precision` is an absolute floor. `beat_baselines` is the one
    that actually matters: the pipeline must score above each named baseline, so
    the gate keeps holding as the corpus grows and the absolute numbers move.
    """
    pipeline = summary.get("pipeline")
    if pipeline is None:
        return ["no assets were scored"]

    failures: list[str] = []

    floor = thresholds.get("min_precision")
    if floor is not None and pipeline["precision"] < floor:
        failures.append(
            f"precision@{summary['k']} is {pipeline['precision']}, below the "
            f"{floor} floor"
        )

    for name in thresholds.get("beat_baselines", []):
        baseline = summary["baselines"].get(name)
        if baseline is None:
            failures.append(
                f"baseline {name!r} was not computed, so the gate cannot check it"
            )
        elif pipeline["precision"] <= baseline["precision"]:
            failures.append(
                f"precision@{summary['k']} is {pipeline['precision']}, which does "
                f"not beat the {name} baseline at {baseline['precision']}"
            )

    return failures


# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.evaluation", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="what one run discarded")
    report.add_argument("--job", required=True)
    report.add_argument("--user", required=True, help="owner id; the session is RLS-scoped")
    report.set_defaults(func=cmd_report)

    score = sub.add_parser("score", help="score a video's latest run")
    score.add_argument("--video", required=True)
    score.add_argument("--job", default=None)
    score.add_argument("--user", required=True)
    score.add_argument(
        "--no-media",
        action="store_true",
        help="skip the baselines that need the source file",
    )
    score.set_defaults(func=cmd_score)

    ablate = sub.add_parser("ablate", help="one component disabled per row")
    ablate.add_argument("--video", required=True)
    ablate.add_argument("--user", required=True)
    ablate.set_defaults(func=cmd_ablate)

    gate = sub.add_parser("gate", help="the CI regression check")
    gate.add_argument("--dir", default=None, help="fixture directory")
    gate.set_defaults(func=cmd_gate)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
