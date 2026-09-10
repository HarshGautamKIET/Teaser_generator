"""Teaser generation orchestration.

Runs the whole pipeline for one job: analyse with AI, validate the output, rank
it, then cut real clips. Each stage updates the job so the frontend can show
progress (FR-018).

Processing is in-process and lightweight by design (ADR-008): no Celery, Redis,
or queue infrastructure.
"""

import logging
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import AIError, AIProvider, AnalysisRequest
from app.config import Settings
from app.domain import (
    DEFAULT_RECORDING_TYPE,
    RECORDING_PROFILES,
    AspectRatio,
    Audience,
    RecordingProfile,
    RecordingType,
    Style,
)
from app.errors import AppError, NotFoundError
from app.media import (
    MediaError,
    Silence,
    assemble,
    detect_silence,
    extract_audio,
    mean_volume_db,
    output_resolution,
    probe,
)
from app.models import Job, JobStatus, Teaser, Video, VideoStatus, new_id
from app.services import (
    caption_service,
    media_service,
    preview_service,
    video_service,
)
from app.services.caption_service import Caption
from app.services.analysis_service import (
    Candidate,
    Narrative,
    validate_candidates,
    validate_narrative,
)
from app.services.pipeline_report import CutQuality, PipelineReport
from app.services.ranking_service import affordable_gap, select_top
from app.storage import GENERATED, UPLOADS, Storage

logger = logging.getLogger(__name__)


class VideoNotReadyError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("VIDEO_NOT_READY", message, 409)


class JobNotCancellableError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("JOB_NOT_CANCELLABLE", message, 409)


class JobCancelled(Exception):
    """Raised inside the pipeline when the owner stopped the run.

    Not an AppError: nothing failed, and it never reaches a client. It exists to
    unwind the pipeline from wherever it happens to be.
    """


# The analysis stage spans the upload, the wait for Gemini to process the file,
# and the analysis itself. Splitting the range gives the longest part of the run
# somewhere to move: everything below UPLOAD_END is the transfer, and reaching
# it means the bytes are there and the model is now watching.
ANALYSIS_START_PROGRESS = 25
UPLOAD_END_PROGRESS = 45
_MB = 1024 * 1024


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
    recording_type: RecordingType | None = None,
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
        recording_type=recording_type.value if recording_type else None,
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


def cancel_job(db: Session, job_id: str) -> Job:
    """Stop a run at its owner's request.

    Only the terminal state is written here, not the teardown: the worker owns
    its own unwinding and notices at the next stage boundary -- or, while the
    source is uploading, at the next chunk, because that stage is long enough
    that waiting it out meant minutes of transfer nobody was waiting for.
    Marking the row immediately is what makes the button honest: the caller sees
    the run stop even though an analysis call already in flight has to return
    first.

    A job that has already finished is rejected rather than quietly accepted.
    Reporting success while changing nothing is worse than a clear 409, and for
    a completed run it would imply its teasers had been thrown away.
    """
    job = get_job(db, job_id)
    if job.status in JobStatus.TERMINAL:
        raise JobNotCancellableError(
            f"This run has already finished (status: {job.status})."
        )

    job.status = JobStatus.CANCELLED
    # Progress is left where it stopped; overwriting it would hide how far the
    # run got before it was stopped.
    job.message = "Cancelled"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    logger.info("Job %s cancelled at %d%%", job.id, job.progress)
    return job


def _advance(db: Session, job: Job, status: str, progress: int, message: str) -> None:
    """Move the job to its next stage, or abort if it has been cancelled.

    Written as a conditional UPDATE rather than three attribute assignments
    because the cancel endpoint writes from a different session. A plain
    assignment would overwrite `cancelled` with the next stage's status, and the
    cancellation would be lost in the window between two stages -- the run would
    carry on to completion having acknowledged a stop it then ignored.

    Guarding inside the same statement that does the write closes that window:
    either the row was not cancelled and this advances it, or it was and zero
    rows match.
    """
    applied = (
        db.query(Job)
        .filter(Job.id == job.id, Job.status != JobStatus.CANCELLED)
        .update(
            {"status": status, "progress": progress, "message": message},
            synchronize_session=False,
        )
    )
    db.commit()
    # The UPDATE bypassed the identity map, so the in-session object still holds
    # the previous stage either way.
    db.refresh(job)

    if not applied:
        raise JobCancelled

    logger.info("Job %s -> %s (%d%%) %s", job.id, status, progress, message)


def _report_upload(db: Session, job: Job):
    """Build the callback the provider drives while it transfers the source.

    Progress and cancellation come from the same write on purpose. `_advance`
    already refuses to move a row somebody has cancelled and raises when it
    finds one, so the call that reports where the upload has got to is also the
    call that discovers it should stop -- and the exception travels back through
    the provider into the read that produced it. Checking separately would mean
    two round trips per chunk to learn one thing.
    """

    def report(sent: int, total: int) -> None:
        if total <= 0 or sent >= total:
            # The bytes have landed. What follows is Gemini processing the file
            # and then watching it, which is the stage's original description.
            _advance(
                db, job, JobStatus.ANALYZING, UPLOAD_END_PROGRESS,
                "Finding strong moments",
            )
            return

        share = sent / total
        _advance(
            db,
            job,
            JobStatus.ANALYZING,
            ANALYSIS_START_PROGRESS
            + int((UPLOAD_END_PROGRESS - ANALYSIS_START_PROGRESS) * share),
            f"Uploading video ({sent / _MB:.1f} of {total / _MB:.1f} MB)",
        )

    return report


@lru_cache(maxsize=None)
def _slot(limit: int) -> threading.BoundedSemaphore:
    """The process-wide permit for the analysis stage.

    Cached rather than built at import so the limit comes from settings, which
    are themselves a cached singleton -- in practice this is one semaphore for
    the life of the process.
    """
    return threading.BoundedSemaphore(limit)


@contextmanager
def _analysis_slot(db: Session, job: Job, limit: int):
    """Hold a permit for the length of the Gemini stage.

    Concurrent uploads do not share an uplink, they divide it: on 2026-08-24
    four runs transferred at roughly 68 KB/s each for half an hour and then all
    four connections dropped together. Sequential runs finish sooner and, more
    to the point, finish at all.

    The wait is only announced when there is one, so a run that walks straight
    in does not flash a message about queueing that was never true.
    """
    permit = _slot(limit)
    if not permit.acquire(blocking=False):
        _advance(
            db, job, JobStatus.ANALYZING, ANALYSIS_START_PROGRESS,
            "Waiting for an upload slot",
        )
        permit.acquire()
    try:
        yield
    finally:
        permit.release()


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
def _profile_for(job: Job) -> RecordingProfile:
    """The pipeline profile this run's recording type asks for.

    A NULL column means the default type, so runs recorded before recording
    types existed resolve to the profile that overrides nothing.
    """
    return RECORDING_PROFILES[
        RecordingType(job.recording_type or DEFAULT_RECORDING_TYPE)
    ]


def _or_default(override: float | int | None, default: float | int):
    """A profile override, or the server setting when it declines to have one.

    Not `override or default`: a profile is allowed to set 0, and that has to
    mean zero rather than falling through to the setting.
    """
    return default if override is None else override


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
    recording_type: RecordingType = DEFAULT_RECORDING_TYPE,
    report: PipelineReport | None = None,
    on_progress=None,
) -> tuple[list[Candidate], Narrative]:
    """Ask the AI for moments, then validate everything it said.

    `max_clip_seconds` is passed rather than read from settings because a job
    may carry its own. Settings is a process-wide cached singleton, so the run
    must never reach that value by mutating it -- one request's preference would
    become every concurrent request's.

    The separation and self-containment rules are stated in the request as well
    as enforced afterwards. Asking for what will be enforced is cheaper than
    silently discarding half of what comes back. The source profile has to be
    applied in both places for the same reason: asking a demo for moments that
    stand alone as completely as a talk's do, and then discarding them for
    failing to, is how the pipeline returned nothing for two of the three
    recording types it is meant to serve.
    """
    profile = RECORDING_PROFILES[recording_type]
    min_self_contained = _or_default(
        profile.min_self_contained, settings.teaser_min_self_contained
    )
    preferred_min = _or_default(
        profile.preferred_min_seconds, settings.teaser_preferred_min_seconds
    )
    preferred_max = _or_default(
        profile.preferred_max_seconds, settings.teaser_preferred_max_seconds
    )

    request = AnalysisRequest(
        video_path=storage.resolve(UPLOADS, video.storage_key),
        audience=audience,
        style=style,
        candidate_count=settings.candidate_count,
        min_duration_seconds=settings.teaser_min_seconds,
        max_duration_seconds=max_clip_seconds,
        # Clamped to the run's own ceiling, so a profile that prefers longer
        # moments than this run allows asks for what it can actually get.
        preferred_min_seconds=min(preferred_min, max_clip_seconds),
        preferred_max_seconds=min(preferred_max, max_clip_seconds),
        video_duration_seconds=video.duration_seconds or 0.0,
        custom_prompt=custom_prompt,
        min_gap_seconds=min_gap_seconds,
        min_self_contained=min_self_contained,
        recording_type=recording_type,
        on_progress=on_progress,
    )
    raw = provider.analyze_video(request)
    duration = video.duration_seconds or 0.0
    # Narrative first: validate_candidates raises when nothing survives, and the
    # summary of a video whose moments were all fragments is still worth having
    # in the log even though this run is about to fail.
    narrative = validate_narrative(raw, duration)
    candidates = validate_candidates(
        raw,
        settings,
        duration,
        max_clip_seconds,
        min_self_contained=min_self_contained,
        report=None if report is None else report.candidates,
    )
    return candidates, narrative


def _discard_media(storage: Storage, keys: list[str]) -> None:
    """Delete clips cut for a run that will never be recorded.

    Best-effort: a file that cannot be removed is worth a log line, never worth
    turning a clean cancellation into an error.
    """
    for key in keys:
        try:
            storage.delete(GENERATED, key)
        except OSError:
            logger.warning("Could not remove abandoned clip %s", key, exc_info=True)


def _source_has_audio(storage: Storage, settings: Settings, video: Video) -> bool:
    """Whether the source carries an audio track at all.

    Answered once and shared, because two later stages need it and each would
    otherwise probe for itself. Assumed false when the file cannot be read: a
    file this stage cannot open is a real problem, but not this stage's to
    report -- cutting owns that failure and has an error code for it, and
    raising here would replace TEASER_GENERATION_FAILED with a generic
    INTERNAL_ERROR from a step the run does not depend on.
    """
    try:
        return probe(
            storage.resolve(UPLOADS, video.storage_key), settings.ffprobe_path
        ).has_audio
    except MediaError:
        logger.warning("Could not inspect %s", video.id, exc_info=True)
        return False


def _find_silences(
    storage: Storage, settings: Settings, video: Video, has_audio: bool
) -> list[Silence]:
    """Locate the pauses this video's clips can be cut on.

    Once per job rather than once per clip: it decodes the whole audio track,
    and the answer is a property of the video, not of any one moment.

    A video with no audio has nothing to snap to, and asking anyway would spend
    a full decode to learn that.
    """
    if settings.teaser_snap_max_shift_seconds <= 0:
        return []

    if not has_audio:
        logger.info("Video %s has no audio track; cut points stay as ranked", video.id)
        return []

    return detect_silence(
        storage.resolve(UPLOADS, video.storage_key),
        video.duration_seconds or 0.0,
        ffmpeg_path=settings.ffmpeg_path,
        noise_db=settings.silence_noise_db,
        min_silence_seconds=settings.silence_min_seconds,
    )


def _caption_clip(
    provider: AIProvider,
    settings: Settings,
    storage: Storage,
    video: Video,
    job: Job,
    teaser_id: str,
    start: float,
    end: float,
    workdir: Path,
) -> tuple[Path | None, list[Caption]]:
    """Transcribe one clip's window and write the subtitle script for it.

    Only the window, never the whole video. A run captions three clips of about
    a minute each, so this is three minutes of audio rather than the two hours
    the analysis step had to watch -- which is the difference between captions
    being an option and being the most expensive thing the pipeline does.

    Best-effort throughout. Captions are burned into a clip that is perfectly
    good without them, so every failure here returns no captions rather than
    costing the run a teaser.
    """
    if not settings.enable_captions:
        return None, []

    try:
        audio = extract_audio(
            storage.resolve(UPLOADS, video.storage_key),
            workdir / f"{teaser_id}.wav",
            start, end,
            ffmpeg_path=settings.ffmpeg_path,
        )
        transcript = provider.transcribe(audio, end - start)
        audio.unlink(missing_ok=True)
    except (MediaError, AIError):
        logger.warning(
            "Could not transcribe the clip at %.1fs; it will have no captions",
            start, exc_info=True,
        )
        return None, []

    captions = caption_service.validate_captions(transcript, end - start)
    width, height = output_resolution(
        job.aspect_ratio or settings.teaser_aspect_ratio
    )
    return (
        caption_service.write_ass(
            captions, workdir / f"{teaser_id}.ass", width, height
        ),
        captions,
    )


def _measure_cut(
    storage: Storage,
    settings: Settings,
    clip_key: str,
    teaser_id: str,
) -> CutQuality | None:
    """How cleanly this clip begins, measured from the file that was written.

    Measured on the finished clip rather than on the source window, because the
    finished clip is what a viewer plays: it has been re-encoded, and if a
    boundary moved between ranking and rendering this is the only place both
    numbers describe the same audio.

    The one quality signal in this project that needs no annotator, no model
    call, and no user -- so it runs on every clip of every run, and a corpus
    accumulates whether or not anyone ever labels anything.

    Returns None rather than raising. The clip already exists and is already
    good; a measurement that fails is a missing row in a report.
    """
    if not settings.enable_cut_quality:
        return None

    path = storage.resolve(GENERATED, clip_key)
    window = settings.cut_quality_window_seconds
    opening = mean_volume_db(path, 0.0, window, settings.ffmpeg_path)
    # The whole clip is the reference. Measuring the opening against a fixed dB
    # floor would report the recording's gain rather than the quality of the cut.
    overall = mean_volume_db(path, 0.0, 10_000.0, settings.ffmpeg_path)
    if opening is None or overall is None:
        return None

    return CutQuality(
        teaser_id=teaser_id,
        opening_db=opening,
        clip_db=overall,
        threshold_db=settings.cut_quality_clean_delta_db,
    )


def _assemble_preview(
    storage: Storage,
    settings: Settings,
    job: Job,
    video: Video,
    selected: list[Candidate],
    summary: str,
    has_audio: bool,
    report: PipelineReport | None = None,
) -> None:
    """Build the run's preview spot, if it is going to have one.

    Best-effort, like captions: the teasers are the run's output and this is an
    extra artifact assembled from moments that were already chosen, so a failure
    here leaves a completed run with clips and no preview.

    Costs no tokens. The moments, their titles and the summary all came from the
    analysis that already ran.
    """
    if not settings.enable_preview:
        return

    width, height = output_resolution(
        job.aspect_ratio or settings.teaser_aspect_ratio
    )
    plan = preview_service.build(
        selected,
        storage.resolve(UPLOADS, video.storage_key),
        summary,
        width,
        height,
    )
    if plan is None:
        if report is not None:
            report.degrade("no_preview_too_few_moments")
        return

    key = f"{video.id}/preview_{job.id}.mp4"
    try:
        with tempfile.TemporaryDirectory(prefix="teaser-preview-") as raw:
            overlay = Path(raw) / "overlay.ass"
            overlay.write_text(plan.overlay, encoding="utf-8")
            result = assemble(
                plan.segments,
                storage.resolve(GENERATED, key),
                width,
                height,
                overlay=overlay,
                source_has_audio=has_audio,
                ffmpeg_path=settings.ffmpeg_path,
                ffprobe_path=settings.ffprobe_path,
            )
    except MediaError:
        if report is not None:
            report.degrade("preview_assembly_failed")
        logger.warning(
            "Could not assemble a preview for job %s", job.id, exc_info=True
        )
        return

    job.preview_storage_key = key
    job.preview_size_bytes = result.size_bytes
    job.preview_duration_seconds = result.info.duration_seconds


def _cut_teasers(
    db: Session,
    storage: Storage,
    settings: Settings,
    provider: AIProvider,
    job: Job,
    video: Video,
    selected: list[Candidate],
    silences: list[Silence],
    report: PipelineReport | None = None,
) -> list[Teaser]:
    """Cut each selected moment. One bad clip must not lose the whole job."""
    teasers: list[Teaser] = []
    failures: list[str] = []
    total = len(selected)

    for index, candidate in enumerate(selected, start=1):
        try:
            _advance(
                db, job, JobStatus.GENERATING,
                70 + int(25 * (index - 1) / max(total, 1)),
                f"Generating teaser {index} of {total}",
            )
        except JobCancelled:
            # Clips already cut are about to be abandoned -- the rows are only
            # added after the loop, so nothing references these files and
            # leaving them would leak a few hundred MB per cancelled run.
            _discard_media(storage, [t.storage_key for t in teasers])
            raise

        teaser_id = new_id()
        # Snapped here rather than before ranking: moving a boundary by a
        # second or two does not change which moments are the strongest, and
        # doing it for the three that were selected instead of every candidate
        # keeps the work proportional to the output.
        start, end = media_service.snap_window(
            candidate.start_seconds, candidate.end_seconds,
            silences, settings, video.duration_seconds or 0.0,
            job.clip_max_seconds,
            report=None if report is None else report.snap,
        )
        with tempfile.TemporaryDirectory(prefix="teaser-captions-") as raw_workdir:
            workdir = Path(raw_workdir)
            subtitles, captions = _caption_clip(
                provider, settings, storage, video, job,
                teaser_id, start, end, workdir,
            )
            try:
                storage_key, result = media_service.generate_teaser(
                    storage, settings, video, teaser_id,
                    start, end,
                    aspect_ratio=job.aspect_ratio,
                    crop_mode=_profile_for(job).crop_mode.value,
                    subtitles=subtitles,
                )
            except AppError as exc:
                failures.append(f"{candidate.title}: {exc.message}")
                logger.warning("Teaser %d/%d failed: %s", index, total, exc.message)
                continue

        if report is not None:
            measured = _measure_cut(storage, settings, storage_key, teaser_id)
            if measured is not None:
                report.cuts.append(measured)

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
                # The snapped window, not the proposed one: this is what the
                # file on disk actually contains, and a row that disagreed with
                # its own clip would make every timestamp in the UI a lie.
                start_seconds=start,
                end_seconds=end,
                score=candidate.score,
                scores=candidate.scores,
                captions=[vars(cue) for cue in captions] or None,
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

    # Accumulated through every stage and written once, in the finally below --
    # so a run that fails still records what it discarded on the way there,
    # which is when the tally is most worth having.
    report = PipelineReport()

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
        recording_type = RecordingType(job.recording_type or DEFAULT_RECORDING_TYPE)
        profile = RECORDING_PROFILES[recording_type]

        # Worked out once and used for both the request and the selection, so
        # the model is asked for exactly the spacing that will be enforced.
        wanted_gap = _or_default(
            profile.min_gap_seconds, settings.teaser_min_gap_seconds
        )
        gap = affordable_gap(
            wanted_gap,
            video.duration_seconds or 0.0,
            wanted_teasers,
            settings.teaser_min_seconds,
        )
        if gap < wanted_gap:
            logger.info(
                "Job %s: gap reduced to %.1fs (%s profile asks for %ds) -- a "
                "%.0fs video cannot space %d clips further apart",
                job.id, gap, recording_type.value, wanted_gap,
                video.duration_seconds or 0.0, wanted_teasers,
            )

        _advance(
            db, job, JobStatus.ANALYZING, ANALYSIS_START_PROGRESS,
            "Finding strong moments",
        )
        with _analysis_slot(db, job, settings.analysis_max_concurrent):
            candidates, narrative = _analyze(
                provider, settings, storage, video,
                Audience(job.audience), Style(job.style),
                max_clip_seconds, job.custom_prompt, gap, recording_type,
                report=report,
                on_progress=_report_upload(db, job),
            )
        job.summary = narrative.summary or None
        job.chapters = [vars(chapter) for chapter in narrative.chapters] or None
        job.keywords = narrative.keywords or None
        if not narrative.summary:
            report.degrade("no_summary")

        _advance(db, job, JobStatus.RANKING, 60, "Ranking candidate moments")
        selected = select_top(candidates, wanted_teasers, gap, report=report.candidates)
        if not selected:
            raise media_service.TeaserGenerationError(
                "No suitable moments remained after ranking."
            )
        if len(selected) < wanted_teasers:
            report.degrade("fewer_clips_than_requested")

        has_audio = _source_has_audio(storage, settings, video)
        if not has_audio:
            report.degrade("no_audio_track")
        silences = _find_silences(storage, settings, video, has_audio)
        teasers = _cut_teasers(
            db, storage, settings, provider, job, video, selected, silences,
            report=report,
        )
        # After the clips, and never instead of them: the preview is assembled
        # from moments that already became teasers, so a run reaches this point
        # having produced its actual output.
        _assemble_preview(
            storage, settings, job, video, selected, job.summary or "", has_audio,
            report=report,
        )

        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.message = f"Generated {len(teasers)} teaser(s)"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %s completed with %d teaser(s)", job.id, len(teasers))

    except JobCancelled:
        # The endpoint already wrote the terminal state; the worker's only job
        # here is to stop touching the row and let the stack unwind.
        logger.info("Job %s stopped at the owner's request", job.id)
    except AIError as exc:
        # AI failure is reported honestly, never replaced with fabricated results.
        _fail(db, job, "AI_ANALYSIS_FAILED", str(exc))
    except AppError as exc:
        _fail(db, job, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure in job %s", job.id)
        _fail(db, job, "INTERNAL_ERROR", f"Unexpected processing error: {exc}")

    _record_report(db, job, report)
    db.refresh(job)
    return job


def _record_report(db: Session, job: Job, report: PipelineReport) -> None:
    """Write the run's tally, whatever happened to the run.

    Outside the try/except above rather than at the end of the happy path,
    because a failed run's tally is the interesting one: "eight proposed, eight
    dropped, all not_self_contained" is the whole diagnosis of a run that
    returned nothing, and recording it only on success would lose it exactly
    when it is needed.

    Never raises. This is a diagnostic, and a run must not be reported as failed
    because its report could not be stored.
    """
    try:
        job.pipeline_report = report.to_dict()
        db.commit()
    except Exception:  # noqa: BLE001
        logger.warning(
            "Could not record the pipeline report for job %s", job.id, exc_info=True
        )
        db.rollback()


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
