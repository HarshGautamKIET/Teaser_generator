"""End-to-end generation: queue a job, run it, and read back real teasers."""

import pytest

from app.ai.base import AIError, AIProvider, RawCandidate, RawCandidateList, RawScores
from app.config import get_settings
from app.database import user_session
from app.media import output_resolution
from app.models import Job, JobStatus, Teaser, Video
from app.services import generation_service
from app.storage import GENERATED, get_storage
from tests.conftest import OWNER_ID, requires_ffmpeg


def scores(value=8.0, self_contained=None):
    """All five dimensions at `value`, with self_contained separable.

    It has to be separable because it is the one dimension that disqualifies a
    moment rather than merely ranking it lower. A fixture spreading scores to
    exercise *ordering* would otherwise push its weakest candidate under the
    self-containment floor and have it disappear, which is a different thing
    being tested.
    """
    return RawScores(
        hook=value, audience_relevance=value, information_value=value,
        engagement=value,
        self_contained=value if self_contained is None else self_contained,
    )


class StubProvider(AIProvider):
    """Returns a fixed response, or raises, without touching the network."""

    def __init__(self, candidates=None, error=None):
        self._candidates = candidates
        self._error = error
        self.calls = 0

    @property
    def name(self) -> str:
        return "stub"

    def analyze_video(self, request):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return RawCandidateList(candidates=self._candidates or [])


def good_candidates():
    """Three non-overlapping moments inside the 8s fixture video.

    The descending scores exist to give ranking something to order. All three
    stay above the self-containment floor -- they are meant to be three usable
    moments of differing quality, not two good ones and a fragment.
    """
    return [
        RawCandidate(start_seconds=0.0, end_seconds=2.5, title="Opening result",
                     hook="A striking claim.", reason="Strong opening.",
                     scores=scores(9.0)),
        RawCandidate(start_seconds=3.0, end_seconds=5.0, title="Middle insight",
                     hook="The surprising part.", reason="Clear demonstration.",
                     scores=scores(7.0)),
        RawCandidate(start_seconds=5.5, end_seconds=7.9, title="Closing point",
                     hook="What it means.", reason="Memorable ending.",
                     scores=scores(5.0, self_contained=8.0)),
    ]


def run(job_id, provider, user_id=OWNER_ID):
    """Execute a job synchronously with its own session, as the worker does.

    The session must be RLS-scoped to the job's owner. A bare
    get_session_factory() session connects as `teaser_app`, which holds no
    privileges on app.* by design, so it cannot see the job at all.
    """
    with user_session(user_id) as db:
        return generation_service.run_job(
            db=db, storage=get_storage(), settings=get_settings(),
            provider=provider, job_id=job_id,
        )


# ----------------------------------------------------------------------
# Queueing
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_generate_queues_a_job(client, uploaded_video):
    response = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["video_id"] == uploaded_video["video_id"]
    assert body["job_id"]


@requires_ffmpeg
def test_generate_rejects_unknown_audience(client, uploaded_video):
    response = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "martians", "style": "promotional"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_for_unknown_video_is_not_found(client):
    response = client.post(
        "/api/videos/missing/generate",
        json={"audience": "general", "style": "informative"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIDEO_NOT_FOUND"


def test_unknown_job_is_not_found(client):
    response = client.get("/api/jobs/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_full_pipeline_produces_playable_teasers(client, uploaded_video, settings):
    video_id = uploaded_video["video_id"]
    job_id = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))
    assert job.status == JobStatus.COMPLETED, job.error_message
    assert job.progress == 100

    body = client.get(f"/api/videos/{video_id}/teasers").json()
    teasers = body["teasers"]
    assert len(teasers) == min(settings.teaser_count, 3)

    best = teasers[0]
    assert best["title"] == "Opening result"
    assert best["rank"] == 1
    assert best["score"] == pytest.approx(9.0)
    # The URL is an ownership-checked endpoint keyed by teaser id. It
    # deliberately no longer leaks the storage key.
    assert best["video_url"] == f"/teasers/{best['id']}/media"
    # A run that names no shape gets the server default, which is widescreen.
    # Per-run shapes are covered in test_aspect_ratio.py.
    assert (best["width"], best["height"]) == output_resolution(
        settings.teaser_aspect_ratio
    )

    # The file behind that URL really exists.
    storage = get_storage()
    with user_session(OWNER_ID) as db:
        key = db.get(Teaser, best["id"]).storage_key
    assert storage.exists(GENERATED, key)
    assert storage.resolve(GENERATED, key).stat().st_size > 0


@requires_ffmpeg
def test_teasers_are_returned_best_first(client, uploaded_video):
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "students", "style": "informative"},
    ).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    teasers = client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"]

    ranks = [t["rank"] for t in teasers]
    scores_desc = [t["score"] for t in teasers]
    assert ranks == sorted(ranks)
    assert scores_desc == sorted(scores_desc, reverse=True)


@requires_ffmpeg
def test_job_status_reports_completion(client, uploaded_video):
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "general", "style": "emotional"},
    ).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    body = client.get(f"/api/jobs/{job_id}").json()

    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["audience"] == "general"
    assert body["style"] == "emotional"
    assert body["ai_provider"] == "stub"
    assert body["error_code"] is None


@requires_ffmpeg
def test_media_endpoint_serves_the_generated_file(client, uploaded_video):
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    url = client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"][0]["video_url"]

    # video_url is relative to the API base, which the frontend prepends.
    response = client.get(f"/api{url}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert len(response.content) > 0


# ----------------------------------------------------------------------
# Failure paths -- never fabricate success (Phase 9)
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_ai_failure_marks_the_job_failed(client, uploaded_video):
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    job = run(job_id, StubProvider(error=AIError("Gemini is unreachable")))

    assert job.status == JobStatus.FAILED
    assert job.error_code == "AI_ANALYSIS_FAILED"
    assert "unreachable" in job.error_message

    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert body["error_code"] == "AI_ANALYSIS_FAILED"
    # No teasers may be invented when the AI failed.
    assert client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"] == []


@requires_ffmpeg
def test_hallucinated_timestamps_fail_the_job_cleanly(client, uploaded_video):
    """Every candidate is out of range, so nothing survives validation."""
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    job = run(job_id, StubProvider([
        RawCandidate(start_seconds=900.0, end_seconds=930.0, title="Not real",
                     hook="Does not exist.", reason="Hallucinated.",
                     scores=scores(9.9)),
    ]))

    assert job.status == JobStatus.FAILED
    assert job.error_code == "NO_VALID_CANDIDATES"


@requires_ffmpeg
def test_empty_ai_response_fails_the_job(client, uploaded_video):
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    job = run(job_id, StubProvider([]))

    assert job.status == JobStatus.FAILED
    assert job.error_code == "NO_VALID_CANDIDATES"


@requires_ffmpeg
def test_one_bad_moment_does_not_lose_the_whole_job(client, uploaded_video):
    """A valid moment alongside an invalid one still yields a teaser."""
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    job = run(job_id, StubProvider([
        RawCandidate(start_seconds=0.0, end_seconds=2.5, title="Good moment",
                     hook="Real.", reason="Valid window.", scores=scores(9.0)),
        RawCandidate(start_seconds=500.0, end_seconds=530.0, title="Bad moment",
                     hook="Fake.", reason="Out of range.", scores=scores(9.9)),
    ]))

    assert job.status == JobStatus.COMPLETED
    teasers = client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"]
    assert [t["title"] for t in teasers] == ["Good moment"]


@requires_ffmpeg
def test_missing_api_key_surfaces_on_the_job(client, uploaded_video, monkeypatch):
    """A job must not vanish silently when the AI is not configured."""
    from app.ai import provider as provider_module
    from app.services import job_runner

    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    def unconfigured():
        raise AIError("GEMINI_API_KEY is not set.")

    monkeypatch.setattr(job_runner, "get_ai_provider", unconfigured)
    job_runner.run_job_in_background(job_id, client.user_id)

    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert body["error_code"] == "AI_NOT_CONFIGURED"


# ----------------------------------------------------------------------
# Job creation guards
# ----------------------------------------------------------------------
def test_teasers_for_unknown_video_is_not_found(client):
    response = client.get("/api/videos/missing/teasers")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIDEO_NOT_FOUND"


@requires_ffmpeg
def test_generate_schedules_background_processing(client, uploaded_video):
    """The endpoint returns immediately and hands the work to the runner."""
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    # The runner is handed the owner as well as the job: it opens its own
    # session and has no request to infer identity from.
    assert client.scheduled_jobs == [(job_id, client.user_id)]

    # Until the runner executes, the job is still queued.
    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "queued"
    assert body["progress"] == 0


@requires_ffmpeg
def test_ffmpeg_failure_fails_the_job_cleanly(client, uploaded_video, settings, monkeypatch):
    """If clip generation breaks, the job reports it instead of half-succeeding."""
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    monkeypatch.setattr(settings, "ffmpeg_path", "ffmpeg-that-does-not-exist")
    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == JobStatus.FAILED
    assert job.error_code == "TEASER_GENERATION_FAILED"
    assert client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"] == []


@requires_ffmpeg
def test_corrupt_source_file_fails_the_job(client, uploaded_video, settings, monkeypatch):
    """A source that FFmpeg cannot read must not produce a broken teaser."""
    from app.storage import UPLOADS, get_storage

    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    # Corrupt the stored video after upload succeeded.
    storage = get_storage()
    with user_session(OWNER_ID) as db:
        video = db.get(Video, uploaded_video["video_id"])
        storage.resolve(UPLOADS, video.storage_key).write_bytes(b"not a video at all")

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == JobStatus.FAILED
    assert job.error_code == "TEASER_GENERATION_FAILED"


# ----------------------------------------------------------------------
# Teaser listing is scoped to one run (audience switching in the demo)
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_second_run_replaces_the_first_in_results(client, uploaded_video):
    """Re-running for a different audience must not mix both runs together."""
    video_id = uploaded_video["video_id"]

    first = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]
    run(first, StubProvider(good_candidates()))

    second = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "business_leaders", "style": "emotional"},
    ).json()["job_id"]
    run(second, StubProvider([
        RawCandidate(start_seconds=1.0, end_seconds=4.0, title="Business angle",
                     hook="Different audience.", reason="Second run.",
                     scores=scores(9.5)),
    ]))

    teasers = client.get(f"/api/videos/{video_id}/teasers").json()["teasers"]

    assert [t["title"] for t in teasers] == ["Business angle"]
    # Ranks must be unique within a run.
    assert len({t["rank"] for t in teasers}) == len(teasers)


@requires_ffmpeg
def test_a_specific_run_can_still_be_requested(client, uploaded_video):
    video_id = uploaded_video["video_id"]

    first = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]
    run(first, StubProvider(good_candidates()))

    second = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "students", "style": "informative"},
    ).json()["job_id"]
    run(second, StubProvider([
        RawCandidate(start_seconds=1.0, end_seconds=4.0, title="Newer run",
                     hook="h", reason="r", scores=scores(9.5)),
    ]))

    older = client.get(
        f"/api/videos/{video_id}/teasers", params={"job_id": first}
    ).json()["teasers"]

    assert [t["title"] for t in older] == [
        "Opening result", "Middle insight", "Closing point",
    ]


@requires_ffmpeg
def test_teasers_before_any_run_is_empty(client, uploaded_video):
    teasers = client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"]

    assert teasers == []
