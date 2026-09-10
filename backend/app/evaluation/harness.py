"""Score a run's real output against annotations, next to the baselines.

Reads what already exists rather than re-running anything. Predictions come from
the `teasers` table -- rows written by a real run, with the timestamps of the
clips actually on disk -- and annotations come either from a hand-written file
or from the product's own feedback table. Scoring therefore costs no Gemini
call, which is what makes it something to run on every prompt change rather than
once.

Two sources of ground truth, in preference order:

1. **Feedback.** Clips the user marked `keep`. Produced as a side effect of
   somebody using the tool on their own material, which makes it better data
   than an annotation exercise and free to collect. Its limitation is that it
   can only contain moments the pipeline already found -- it can prove a
   selected clip was wrong, never that an unselected moment was missed. So
   recall against feedback is not meaningful and is reported but not gated.
2. **Annotation files.** `backend/evaluation/ground_truth/<id>.json`, written by
   hand against the source. Expensive, and the only thing that can measure a
   miss.

Both are handled, and which one produced a row is stated in the result: a table
that silently mixed them would report a recall of 1.0 for the feedback rows and
make the average meaningless.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.evaluation.baselines import (
    audio_peak_spans,
    keyword_spans,
    random_spans,
    uniform_spans,
)
from app.evaluation.metrics import (
    DEFAULT_KS,
    GroundTruthSpan,
    RetrievalScores,
    retrieval_scores,
)
from app.models import Job, JobStatus, Teaser, TeaserFeedback, Verdict, Video

logger = logging.getLogger(__name__)

Span = tuple[float, float]

#: Which baselines can run without media on disk. The CI gate uses only these,
#: so the fixture corpus needs annotations and predictions, never video files.
OFFLINE_BASELINES = ("uniform", "random")


@dataclass
class GroundTruth:
    """Annotations for one source video."""

    asset_id: str
    duration_seconds: float
    spans: list[GroundTruthSpan] = field(default_factory=list)
    #: "annotation" or "feedback". Carried because the two support different
    #: claims -- see the module docstring.
    origin: str = "annotation"
    note: str = ""

    @classmethod
    def from_file(cls, path: Path) -> "GroundTruth":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            asset_id=payload["asset_id"],
            duration_seconds=float(payload["duration_seconds"]),
            spans=[GroundTruthSpan(**span) for span in payload.get("spans", [])],
            origin=payload.get("origin", "annotation"),
            note=payload.get("note", ""),
        )


@dataclass
class AssetResult:
    """One row of the results table."""

    asset_id: str
    origin: str
    scores: dict[int, RetrievalScores] = field(default_factory=dict)
    baselines: dict[str, dict[int, RetrievalScores]] = field(default_factory=dict)
    predictions: int = 0
    annotations: int = 0
    #: True when the asset has annotations but no run to score. Reported rather
    #: than skipped: quietly dropping it turns an evaluation over three assets
    #: into one over two, and improves the headline for the wrong reason.
    missing_run: bool = False
    #: Baselines that could not be computed, and why. A baseline that silently
    #: did not run reads as one the pipeline beat.
    unavailable: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "origin": self.origin,
            "predictions": self.predictions,
            "annotations": self.annotations,
            "missing_run": self.missing_run,
            "scores": {k: s.to_dict() for k, s in sorted(self.scores.items())},
            "baselines": {
                name: {k: s.to_dict() for k, s in sorted(rows.items())}
                for name, rows in sorted(self.baselines.items())
            },
            "unavailable": dict(sorted(self.unavailable.items())),
        }


# ----------------------------------------------------------------------
# Where predictions come from
# ----------------------------------------------------------------------
def predictions_from_db(
    db: Session, video_id: str, job_id: str | None = None
) -> list[Span]:
    """The spans a real run produced, best-ranked first.

    Rank order, not chronological. Precision@K takes the first K, so the order
    has to be the pipeline's own confidence -- scoring a chronological list
    would measure a different system than the one that shipped.
    """
    query = (
        db.query(Teaser.start_seconds, Teaser.end_seconds)
        .join(Job, Job.id == Teaser.job_id)
        .filter(Teaser.video_id == video_id, Job.status == JobStatus.COMPLETED)
    )
    if job_id is not None:
        query = query.filter(Teaser.job_id == job_id)
    else:
        latest = (
            db.query(Job.id)
            .filter(Job.video_id == video_id, Job.status == JobStatus.COMPLETED)
            .order_by(Job.created_at.desc())
            .first()
        )
        if latest is None:
            return []
        query = query.filter(Teaser.job_id == latest[0])

    return [(start, end) for start, end in query.order_by(Teaser.rank.asc()).all()]


def ground_truth_from_feedback(db: Session, video_id: str) -> GroundTruth | None:
    """Annotations derived from what the user kept.

    A clip marked `keep` is a span that should have been selected. Clips marked
    `discard` are deliberately not turned into negative annotations: these
    metrics score what a run returned against what it should have returned, and
    a "should not" has no place in that set -- it is already counted, as a
    prediction that matched nothing.

    Returns None when nobody has kept anything for this video, rather than an
    empty GroundTruth. Zero annotations would score every run at precision 0.0
    and drag a corpus average down with a row that means "unlabelled".
    """
    video = db.get(Video, video_id)
    if video is None or not video.duration_seconds:
        return None

    rows = (
        db.query(Teaser.start_seconds, Teaser.end_seconds)
        .join(TeaserFeedback, TeaserFeedback.teaser_id == Teaser.id)
        .join(Job, Job.id == Teaser.job_id)
        .filter(
            Teaser.video_id == video_id,
            TeaserFeedback.verdict == Verdict.KEEP,
            Job.status == JobStatus.COMPLETED,
        )
        .order_by(Teaser.start_seconds.asc())
        .all()
    )
    if not rows:
        return None

    return GroundTruth(
        asset_id=video_id,
        duration_seconds=video.duration_seconds,
        spans=[GroundTruthSpan(start=start, end=end, why="kept by the user")
               for start, end in rows],
        origin="feedback",
    )


def load_ground_truth_dir(directory: Path) -> list[GroundTruth]:
    """Every annotation file in a directory, sorted for a stable report order."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return [GroundTruth.from_file(path) for path in sorted(directory.glob("*.json"))]


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------
def score(
    predictions: list[Span],
    truth: GroundTruth,
    ks: tuple[int, ...] = DEFAULT_KS,
    source: Path | None = None,
    captions: list[tuple[float, float, str]] | None = None,
    ffmpeg_path: str = "ffmpeg",
) -> AssetResult:
    """Score one asset's predictions, and every baseline that can run.

    `source` and `captions` are optional because two of the four baselines need
    neither. Omitting them produces a report with `audio_peak` and `keyword`
    listed under `unavailable` with a reason, which is the honest outcome -- the
    alternative, dropping the rows, reads as "the pipeline beat every baseline".
    """
    result = AssetResult(
        asset_id=truth.asset_id,
        origin=truth.origin,
        predictions=len(predictions),
        annotations=len(truth.spans),
        missing_run=not predictions,
    )
    result.scores = {k: retrieval_scores(predictions, truth.spans, k) for k in ks}

    largest = max(ks)
    candidates: dict[str, list[Span]] = {
        "uniform": uniform_spans(truth.duration_seconds, largest),
        "random": random_spans(truth.duration_seconds, largest),
    }

    if captions:
        candidates["keyword"] = keyword_spans(
            captions, truth.duration_seconds, largest
        )
    else:
        result.unavailable["keyword"] = "no transcript available for this asset"

    if source is not None and Path(source).is_file():
        peaks = audio_peak_spans(
            Path(source), truth.duration_seconds, largest, ffmpeg_path
        )
        if peaks:
            candidates["audio_peak"] = peaks
        else:
            result.unavailable["audio_peak"] = "the audio track could not be measured"
    else:
        result.unavailable["audio_peak"] = "the source media is not on disk"

    for name, spans in candidates.items():
        result.baselines[name] = {
            k: retrieval_scores(spans, truth.spans, k) for k in ks
        }
    return result


def summarise(results: list[AssetResult], k: int) -> dict[str, Any]:
    """Corpus-level averages at one K, for the pipeline and each baseline.

    Assets with no run are counted, at zero. An evaluation that skipped them
    would report the average of the assets that happened to work, which climbs
    every time a run fails.
    """
    scored = [r for r in results if k in r.scores]
    if not scored:
        return {"k": k, "assets": 0, "pipeline": None, "baselines": {}}

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    baseline_names = sorted({name for r in scored for name in r.baselines})
    return {
        "k": k,
        "assets": len(scored),
        "pipeline": {
            "precision": mean([r.scores[k].precision for r in scored]),
            "recall": mean([r.scores[k].recall for r in scored]),
            "f1": mean([r.scores[k].f1 for r in scored]),
            "mean_iou": mean([r.scores[k].mean_iou for r in scored]),
        },
        "baselines": {
            name: {
                "precision": mean(
                    [r.baselines[name][k].precision for r in scored if name in r.baselines]
                ),
                "f1": mean(
                    [r.baselines[name][k].f1 for r in scored if name in r.baselines]
                ),
                # How many assets contributed. A baseline computed on one asset
                # out of five is not comparable with one computed on all five,
                # and the average alone would not show it.
                "assets": sum(1 for r in scored if name in r.baselines),
            }
            for name in baseline_names
        },
    }
