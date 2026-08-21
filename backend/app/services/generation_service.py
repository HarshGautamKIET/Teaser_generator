"""Teaser generation orchestration.

Runs the whole pipeline for one job: analyse with AI, validate the output, rank
it, then cut real clips. Each stage updates the job so the frontend can show
progress (FR-018).

Processing is in-process and lightweight by design (ADR-008): no Celery, Redis,
or queue infrastructure.
"""

import logging
from datetime import datetime, timezone
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import AIError, AIProvider, AnalysisRequest
from app.config import Settings
from app.domain import AspectRatio, Audience, Style
from app.errors import AppError, NotFoundError
from app.models import Job, JobStatus, Teaser, Video, VideoStatus, new_id
from app.services import media_service, video_service
from app.services.analysis_service import Candidate, validate_candidates
from app.services.ranking_service import affordable_gap, select_top
from app.storage import UPLOADS, Storage

logger = logging.getLogger(__name__)


class VideoNotReadyError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("VIDEO_NOT_READY", message, 409)


# ----------------------------------------------------------------------
# Job lifecycle
# ----------------------------------------------------------------------
def create_job(
    db: Session,
    video_id: str,
    audience: Audience,
    style: Style,
    user_id: str,
    teaser_count: int | None = None,
    clip_max_seconds: int | None = None,
    aspect_ratio: AspectRatio | None = None,
    custom_prompt: str | None = None,
) -> Job:
    """Record a queued job for a video that is ready to process.

    `video_id` is looked up through the caller's own session, so a video that
    belongs to someone else is not "forbidden" here -- it simply does not exist,
    and surfaces as VIDEO_NOT_FOUND. That is deliberate: it leaks nothing about
    whether the id is real.
    """
    video = video_service.get_video(db, video_id)
    if video.status != VideoStatus.READY or not video.duration_seconds:
        raise VideoNotReadyError(
            f"Video {video_id} is not ready for processing (status: {video.status})."
        )

    job = Job(
        id=new_id(),
        user_id=user_id,
        video_id=video.id,
        audience=audience.value,
        style=style.value,
        teaser_count=teaser_count,
        clip_max_seconds=clip_max_seconds,
        aspect_ratio=aspect_ratio.value if aspect_ratio else None,
        # Blank-only direction is stored as absent, so history does not show an
        # empty quote where no direction was given.
        custom_prompt=(custom_prompt or "").strip() or None,
        status=JobStatus.QUEUED,
        progress=0,
        message="Queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(
        "Created job %s for video %s (%s / %s)",
        job.id, video.id, audience.value, style.value,
    )
    return job


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError("JOB_NOT_FOUND", f"No job found with id {job_id}.")
    return job


def _advance(db: Session, job: Job, status: str, progress: int, message: str) -> None:
    job.status = status
    job.progress = progress
    job.message = message
    db.commit()
    logger.info("Job %s -> %s (%d%%) %s", job.id, status, progress, message)


def _fail(db: Session, job: Job, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.message = "Failed"
    job.error_code = code
    job.error_message = message
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.error("Job %s failed [%s]: %s", job.id, code, message)


# ----------------------------------------------------------------------
# Pipeline stages
# ----------------------------------------------------------------------
def _analyze(
    provider: AIProvider,
    settings: Settings,
    storage: Storage,
    video: Video,
    audience: Audience,
    style: Style,
    max_clip_seconds: int,
    custom_prompt: str | None = None,
    min_gap_seconds: float = 0.0,
) -> list[Candidate]:
    """Ask the AI for moments, then validate everything it said.

    `max_clip_seconds` is passed rather than read from settings because a job
    may carry its own. Settings is a process-wide cached singleton, so the run
    must never reach that value by mutating it -- one request's preference would
    become every concurrent request's.

    The separation and self-containment rules are stated in the request as well
    as enforced afterwards. Asking for what will be enforced is cheaper than
    silently discarding half of what comes back.
    """
    request = AnalysisRequest(
        video_path=storage.resolve(UPLOADS, video.storage_key),
        audience=audience,
        style=style,
        candidate_count=settings.candidate_count,
        min_duration_seconds=settings.teaser_min_seconds,
        max_duration_seconds=max_clip_seconds,
        preferred_min_seconds=min(
            settings.teaser_preferred_min_seconds, max_clip_seconds
        ),
        preferred_max_seconds=min(
            settings.teaser_preferred_max_seconds, max_clip_seconds
        ),
        video_duration_seconds=video.duration_seconds or 0.0,
        custom_prompt=custom_prompt,
        min_gap_seconds=min_gap_seconds,
        min_self_contained=settings.teaser_min_self_contained,
    )
    raw = provider.analyze_video(request)
    return validate_candidates(
        raw, settings, video.duration_seconds or 0.0, max_clip_seconds
    )


def _cut_teasers(
    db: Session,
    storage: Storage,
    settings: Settings,
    job: Job,
    video: Video,
    selected: list[Candidate],
) -> list[Teaser]:
    """Cut each selected moment. One bad clip must not lose the whole job."""
    teasers: list[Teaser] = []
    failures: list[str] = []
    total = len(selected)

    for index, candidate in enumerate(selected, start=1):
        _advance(
            db, job, JobStatus.GENERATING,
            70 + int(25 * (index - 1) / max(total, 1)),
            f"Generating teaser {index} of {total}",
        )

        teaser_id = new_id()
        try:
            storage_key, result = media_service.generate_teaser(
                storage, settings, video, teaser_id,
                candidate.start_seconds, candidate.end_seconds,
                aspect_ratio=job.aspect_ratio,
            )
        except AppError as exc:
            failures.append(f"{candidate.title}: {exc.message}")
            logger.warning("Teaser %d/%d failed: %s", index, total, exc.message)
            continue

        teasers.append(
            Teaser(
                id=teaser_id,
                user_id=job.user_id,
                job_id=job.id,
                video_id=video.id,
                rank=len(teasers) + 1,
                title=candidate.title,
                hook=candidate.hook,
                reason=candidate.reason,
                start_seconds=candidate.start_seconds,
                end_seconds=candidate.end_seconds,
                score=candidate.score,
                scores=candidate.scores,
                storage_key=storage_key,
                size_bytes=result.size_bytes,
                width=result.info.width,
                height=result.info.height,
                duration_seconds=result.info.duration_seconds,
            )
        )

    if not teasers:
        raise media_service.TeaserGenerationError(
            "No teaser clips could be generated. " + " | ".join(failures)
        )

    db.add_all(teasers)
    db.commit()
    if failures:
        logger.warning("Job %s: %d clip(s) failed", job.id, len(failures))
    return teasers


# ----------------------------------------------------------------------
# Entry point for background processing
# ----------------------------------------------------------------------
def run_job(
    db: Session,
    storage: Storage,
    settings: Settings,
    provider: AIProvider,
    job_id: str,
) -> Job:
    """Execute a queued job to completion. Never raises; failures land on the job."""
    job = get_job(db, job_id)
    job.ai_provider = provider.name
    # Clear any earlier failure so a retried job is not misreported.
    job.error_code = None
    job.error_message = None

    try:
        _advance(db, job, JobStatus.VALIDATING, 10, "Checking the video")
        video = video_service.get_video(db, job.video_id)
        if video.status != VideoStatus.READY or not video.duration_seconds:
            raise VideoNotReadyError(
                f"Video {video.id} is not ready for processing."
            )

        # A job may carry its own pipeline settings; NULL means the server default.
        max_clip_seconds = job.clip_max_seconds or settings.teaser_max_seconds
        wanted_teasers = job.teaser_count or settings.teaser_count

        # Worked out once and used for both the request and the selection, so
        # the model is asked for exactly the spacing that will be enforced.
        gap = affordable_gap(
            settings.teaser_min_gap_seconds,
            video.duration_seconds or 0.0,
            wanted_teasers,
            settings.teaser_min_seconds,
        )
        if gap < settings.teaser_min_gap_seconds:
            logger.info(
                "Job %s: gap reduced to %.1fs (configured %ds) -- a %.0fs video "
                "cannot space %d clips further apart",
                job.id, gap, settings.teaser_min_gap_seconds,
                video.duration_seconds or 0.0, wanted_teasers,
            )

        _advance(db, job, JobStatus.ANALYZING, 25, "Finding strong moments")
        candidates = _analyze(
            provider, settings, storage, video,
            Audience(job.audience), Style(job.style),
            max_clip_seconds, job.custom_prompt, gap,
        )

        _advance(db, job, JobStatus.RANKING, 60, "Ranking candidate moments")
        selected = select_top(candidates, wanted_teasers, gap)
        if not selected:
            raise media_service.TeaserGenerationError(
                "No suitable moments remained after ranking."
            )

        teasers = _cut_teasers(db, storage, settings, job, video, selected)

        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.message = f"Generated {len(teasers)} teaser(s)"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %s completed with %d teaser(s)", job.id, len(teasers))

    except AIError as exc:
        # AI failure is reported honestly, never replaced with fabricated results.
        _fail(db, job, "AI_ANALYSIS_FAILED", str(exc))
    except AppError as exc:
        _fail(db, job, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure in job %s", job.id)
        _fail(db, job, "INTERNAL_ERROR", f"Unexpected processing error: {exc}")

    db.refresh(job)
    return job


def list_teasers(
    db: Session, video_id: str, job_id: str | None = None
) -> list[Teaser]:
    """Teasers from a single run, best-first.

    A video can be processed repeatedly for different audiences, so results are
    scoped to one job: the named one, or the latest completed run. Returning
    every job's teasers together would mix audiences in one list.
    """
    video_service.get_video(db, video_id)

    if job_id is None:
        latest = (
            db.query(Job)
            .filter(Job.video_id == video_id, Job.status == JobStatus.COMPLETED)
            .order_by(Job.created_at.desc())
            .first()
        )
        if latest is None:
            return []
        job_id = latest.id
    else:
        job = get_job(db, job_id)
        if job.video_id != video_id:
            raise NotFoundError(
                "JOB_NOT_FOUND", f"Job {job_id} does not belong to video {video_id}."
            )

    return (
        db.query(Teaser)
        .filter(Teaser.job_id == job_id)
        .order_by(Teaser.rank.asc())
        .all()
    )


class JobWithContext(NamedTuple):
    job: Job
    filename: str
    teaser_count: int


def list_jobs(db: Session, video_id: str | None = None) -> list[JobWithContext]:
    """Every run the caller owns, newest first, optionally for one video.

    The source filename is joined in because a run listing that only showed job
    ids would be unreadable, and the clip count because "how many did it make"
    is the first thing anyone asks of a finished run.
    """
    counts = dict(
        db.query(Teaser.job_id, func.count(Teaser.id)).group_by(Teaser.job_id).all()
    )

    query = db.query(Job, Video.original_filename).join(Video, Video.id == Job.video_id)
    if video_id is not None:
        query = query.filter(Job.video_id == video_id)

    return [
        JobWithContext(job, filename, counts.get(job.id, 0))
        for job, filename in query.order_by(Job.created_at.desc()).all()
    ]


class TeaserWithContext(NamedTuple):
    teaser: Teaser
    filename: str
    audience: str
    style: str


def list_all_teasers(db: Session) -> list[TeaserWithContext]:
    """Every clip the caller owns, newest run first, best clip first within a run.

    Unlike `list_teasers` this deliberately spans jobs: the library is a shelf of
    finished work, not the result of one run, so mixing audiences is the point
    rather than a hazard. Each row carries the audience and style that produced
    it so the mixture stays legible.
    """
    rows = (
        db.query(Teaser, Video.original_filename, Job.audience, Job.style)
        .join(Video, Video.id == Teaser.video_id)
        .join(Job, Job.id == Teaser.job_id)
        .order_by(Teaser.created_at.desc(), Teaser.rank.asc())
        .all()
    )
    return [TeaserWithContext(*row) for row in rows]
