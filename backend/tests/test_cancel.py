"""Cancelling a run.

The button existed in the UI long before the endpoint did: it stopped the
frontend polling and left the worker running. These tests are mostly about the
difference between those two things -- that a cancelled run really does stop
touching the database, stop cutting clips, and stay cancelled afterwards.
"""

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.database import unscoped_session, user_session
from app.models import Job, JobStatus, Teaser
from app.services import generation_service, media_service
from app.storage import GENERATED, get_storage
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run


def queue_job(client, video_id, **body):
    """Queue a run and return its id. The worker is stubbed out by the fixture,
    so the job stays `queued` until a test runs it explicitly."""
    response = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "developers", "style": "promotional", **body},
    )
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def cancel_out_of_band(job_id):
    """Cancel the way the endpoint does: a different session from the worker's.

    Cancelling through the worker's own session would prove nothing -- the whole
    hazard is that the two writes race on the same row.
    """
    with user_session(OWNER_ID) as db:
        return generation_service.cancel_job(db, job_id)


def job_status(job_id):
    with user_session(OWNER_ID) as db:
        return db.get(Job, job_id).status


# ----------------------------------------------------------------------
# The endpoint
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_cancel_marks_the_job_cancelled(client, uploaded_video):
    job_id = queue_job(client, uploaded_video["video_id"])

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["job_id"] == job_id


@requires_ffmpeg
def test_cancel_keeps_the_progress_it_reached(client, uploaded_video):
    """How far a run got before being stopped is worth keeping."""
    job_id = queue_job(client, uploaded_video["video_id"])
    with user_session(OWNER_ID) as db:
        db.get(Job, job_id).progress = 60
        db.commit()

    body = client.post(f"/api/jobs/{job_id}/cancel").json()

    assert body["progress"] == 60


def test_cancel_unknown_job_is_not_found(client):
    response = client.post("/api/jobs/missing/cancel")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


@requires_ffmpeg
def test_cancel_requires_authentication(anonymous_client, client, uploaded_video):
    job_id = queue_job(client, uploaded_video["video_id"])

    response = anonymous_client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 401


@requires_ffmpeg
def test_cannot_cancel_another_users_job(client, other_client, uploaded_video):
    """Not "forbidden" -- not found. A 403 would confirm the id is real."""
    job_id = queue_job(client, uploaded_video["video_id"])

    response = other_client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 404
    assert job_status(job_id) == JobStatus.QUEUED


@requires_ffmpeg
def test_cancelling_a_finished_run_is_rejected(client, uploaded_video):
    """Accepting it would report success while changing nothing, and imply the
    completed run's teasers had been discarded."""
    job_id = queue_job(client, uploaded_video["video_id"])
    run(job_id, StubProvider(good_candidates()))
    assert job_status(job_id) == JobStatus.COMPLETED

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JOB_NOT_CANCELLABLE"
    assert job_status(job_id) == JobStatus.COMPLETED


@requires_ffmpeg
def test_cancelling_twice_is_rejected(client, uploaded_video):
    job_id = queue_job(client, uploaded_video["video_id"])
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 200

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 409


# ----------------------------------------------------------------------
# The worker actually stops
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_cancelled_before_pickup_never_calls_the_ai(client, uploaded_video):
    """The expensive call must not happen at all. A cancel that still burns the
    Gemini quota it was pressed to save is not a cancel."""
    job_id = queue_job(client, uploaded_video["video_id"])
    cancel_out_of_band(job_id)

    provider = StubProvider(good_candidates())
    run(job_id, provider)

    assert provider.calls == 0
    assert job_status(job_id) == JobStatus.CANCELLED


@requires_ffmpeg
def test_cancel_during_analysis_produces_no_teasers(client, uploaded_video):
    """Analysis is one long call that cannot be interrupted, so the stop lands
    at the next stage boundary -- before anything is cut."""
    job_id = queue_job(client, uploaded_video["video_id"])

    class CancellingProvider(StubProvider):
        def analyze_video(self, request):
            result = super().analyze_video(request)
            cancel_out_of_band(job_id)
            return result

    run(job_id, CancellingProvider(good_candidates()))

    assert job_status(job_id) == JobStatus.CANCELLED
    with user_session(OWNER_ID) as db:
        assert db.query(Teaser).filter(Teaser.job_id == job_id).count() == 0


@requires_ffmpeg
def test_cancel_does_not_overwrite_a_finished_run(client, uploaded_video):
    """The guard is on the write, not just on a prior read: a stage that
    completes after the cancel lands must not resurrect the job."""
    job_id = queue_job(client, uploaded_video["video_id"])
    run(job_id, StubProvider(good_candidates()))

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        with pytest.raises(generation_service.JobNotCancellableError):
            generation_service.cancel_job(db, job_id)
        db.refresh(job)
        assert job.status == JobStatus.COMPLETED


@requires_ffmpeg
def test_cancel_mid_generation_discards_the_clips_already_cut(
    client, uploaded_video, monkeypatch
):
    """Rows are only written after the whole loop, so a clip cut before the
    cancel is referenced by nothing. Left on disk it would leak silently."""
    job_id = queue_job(client, uploaded_video["video_id"], teaser_count=3)
    storage = get_storage()
    cut_keys: list[str] = []
    real_generate = media_service.generate_teaser

    def generate_then_cancel(*args, **kwargs):
        storage_key, result = real_generate(*args, **kwargs)
        cut_keys.append(storage_key)
        # Stop the run once the first clip exists, so there is something to leak.
        cancel_out_of_band(job_id)
        return storage_key, result

    monkeypatch.setattr(media_service, "generate_teaser", generate_then_cancel)
    run(job_id, StubProvider(good_candidates()))

    assert cut_keys, "expected at least one clip to be cut before the cancel"
    assert job_status(job_id) == JobStatus.CANCELLED

    with user_session(OWNER_ID) as db:
        assert db.query(Teaser).filter(Teaser.job_id == job_id).count() == 0
    for key in cut_keys:
        assert not storage.exists(GENERATED, key), f"{key} was left behind"


# ----------------------------------------------------------------------
# It stays cancelled
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_restart_sweep_leaves_cancelled_jobs_alone(client, uploaded_video):
    """reconcile_stranded_jobs() fails anything non-terminal on boot. Before
    migration 0007 that included `cancelled`, so the first restart relabelled a
    clean stop as "the server restarted while this job was running"."""
    job_id = queue_job(client, uploaded_video["video_id"])
    cancel_out_of_band(job_id)

    with unscoped_session() as db:
        db.execute(select(func.app.reconcile_stranded_jobs())).scalar_one()
        db.commit()

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.CANCELLED
        assert job.error_code is None


@requires_ffmpeg
def test_restart_sweep_still_fails_genuinely_stranded_jobs(client, uploaded_video):
    """The complement of the test above: narrowing the sweep must not have
    stopped it doing its actual job."""
    job_id = queue_job(client, uploaded_video["video_id"])
    with user_session(OWNER_ID) as db:
        db.get(Job, job_id).status = JobStatus.ANALYZING
        db.commit()

    with unscoped_session() as db:
        db.execute(select(func.app.reconcile_stranded_jobs())).scalar_one()
        db.commit()

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.FAILED
        assert job.error_code == "INTERRUPTED"


@requires_ffmpeg
def test_cancelled_run_is_not_offered_as_the_latest_teasers(
    client, uploaded_video
):
    """`GET /videos/{id}/teasers` falls back to the latest *completed* run. A
    cancelled one must not shadow it."""
    video_id = uploaded_video["video_id"]
    finished = queue_job(client, video_id)
    completed = run(finished, StubProvider(good_candidates()))
    assert completed.status == JobStatus.COMPLETED

    cancelled = queue_job(client, video_id)
    cancel_out_of_band(cancelled)

    body = client.get(f"/api/videos/{video_id}/teasers").json()

    with user_session(OWNER_ID) as db:
        expected = db.query(Teaser).filter(Teaser.job_id == finished).count()
    assert expected > 0
    assert len(body["teasers"]) == expected


@requires_ffmpeg
def test_settings_are_not_mutated_by_a_cancelled_run(client, uploaded_video):
    """Settings is a process-wide cached singleton; a cancelled run must leave
    it exactly as it found it."""
    before = get_settings().teaser_count
    job_id = queue_job(client, uploaded_video["video_id"], teaser_count=1)
    cancel_out_of_band(job_id)
    run(job_id, StubProvider(good_candidates()))

    assert get_settings().teaser_count == before
