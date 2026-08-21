"""Background execution of generation jobs.

Deliberately simple (ADR-008): the work runs in a FastAPI background task with
its own database session, because the request-scoped session is already closed
by the time the job starts.

That session still has to be scoped to the job's owner. A background task has no
request and no access token, so the user id is passed in explicitly and used to
open an RLS-scoped session -- the job runs with exactly the privileges the person
who started it had, and cannot touch anyone else's rows.
"""

import logging

from app.ai import AIError, get_ai_provider
from app.config import get_settings
from app.database import user_session
from app.models import Job, JobStatus, Video
from app.services import generation_service, ingest_service
from app.storage import get_storage

logger = logging.getLogger(__name__)


def fetch_video_in_background(video_id: str, user_id: str) -> None:
    """Download a video's source URL. Failures land on the video row."""
    with user_session(user_id) as db:
        video = db.get(Video, video_id)
        if video is None:
            logger.warning("Fetch requested for unknown video %s", video_id)
            return
        try:
            ingest_service.fetch_into_video(
                db=db, storage=get_storage(), settings=get_settings(), video=video
            )
        except Exception:  # noqa: BLE001
            logger.exception("Background fetch for video %s crashed", video_id)


def run_job_in_background(job_id: str, user_id: str) -> None:
    """Execute a queued job. Any failure is recorded on the job, not raised."""
    settings = get_settings()
    with user_session(user_id) as db:
        try:
            try:
                provider = get_ai_provider()
            except AIError as exc:
                # A missing API key must surface on the job, not vanish in a thread.
                job = db.get(Job, job_id)
                if job is not None:
                    job.status = JobStatus.FAILED
                    job.message = "Failed"
                    job.error_code = "AI_NOT_CONFIGURED"
                    job.error_message = str(exc)
                    db.commit()
                logger.error("Job %s could not start: %s", job_id, exc)
                return

            generation_service.run_job(
                db=db,
                storage=get_storage(),
                settings=settings,
                provider=provider,
                job_id=job_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Background job %s crashed", job_id)
