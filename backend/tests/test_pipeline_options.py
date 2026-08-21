"""Per-run pipeline settings.

Teaser count and clip length used to be server-wide, so two people sharing a
deployment could not disagree about them. They are now per job, defaulting to
the server value when a request says nothing.

The property worth protecting is that the default really is a default: a
request that omits them must behave exactly as it did before, and a request
that sets them must not change what any other request sees. Settings is an
lru_cached singleton, so "apply the override by mutating settings" would pass a
naive test and corrupt every concurrent run.
"""

import pytest

from app.ai.base import RawCandidate, RawCandidateList
from app.config import get_settings
from app.database import user_session
from app.models import Job
from app.services.analysis_service import NoValidCandidatesError, validate_candidates
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run, scores


def queue(client, video_id, **body):
    payload = {"audience": "developers", "style": "promotional", **body}
    return client.post(f"/api/videos/{video_id}/generate", json=payload)


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
@requires_ffmpeg
@pytest.mark.parametrize(
    "field,value",
    [
        ("teaser_count", 0),
        ("teaser_count", 11),
        ("teaser_count", -1),
        ("clip_max_seconds", 4),
        ("clip_max_seconds", 181),
    ],
)
def test_out_of_range_options_are_rejected(client, uploaded_video, field, value):
    response = queue(client, uploaded_video["video_id"], **{field: value})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@requires_ffmpeg
def test_options_are_optional(client, uploaded_video):
    """Omitting them stores NULL, which is what makes them fall back."""
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        assert job.teaser_count is None
        assert job.clip_max_seconds is None


@requires_ffmpeg
def test_options_are_stored_on_the_job(client, uploaded_video):
    job_id = queue(
        client, uploaded_video["video_id"], teaser_count=2, clip_max_seconds=30
    ).json()["job_id"]

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        assert job.teaser_count == 2
        assert job.clip_max_seconds == 30


# ----------------------------------------------------------------------
# Effect on a real run
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_teaser_count_caps_how_many_clips_are_cut(client, uploaded_video):
    """The stub offers three usable moments; the job asks for one."""
    video_id = uploaded_video["video_id"]
    job_id = queue(client, video_id, teaser_count=1).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))
    assert job.status == "completed", job.error_message

    teasers = client.get(f"/api/videos/{video_id}/teasers").json()["teasers"]
    assert len(teasers) == 1
    # The one kept is the best, not merely the first offered.
    assert teasers[0]["title"] == "Opening result"


@requires_ffmpeg
def test_clip_max_seconds_rejects_moments_that_are_too_long(client, uploaded_video):
    """Every stub candidate is at least 2s, so a 5s ceiling keeps them all..."""
    video_id = uploaded_video["video_id"]
    job_id = queue(client, video_id, clip_max_seconds=5).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == "completed", job.error_message
    assert client.get(f"/api/videos/{video_id}/teasers").json()["teasers"]


# The clip ceiling is exercised directly rather than over HTTP. The suite runs
# with TEASER_MAX_SECONDS=5 and the API refuses an override below 5, so through
# the endpoint an override can never be *stricter* than the server default in
# this environment -- there is no request that would prove anything. The rule
# itself lives in validate_candidates, so that is where it is checked.
def candidate(length: float) -> RawCandidate:
    return RawCandidate(
        start_seconds=0.0, end_seconds=length, title="A moment",
        hook="A moment worth clipping.", reason="Chosen for the test.",
        scores=scores(9.0),
    )


def test_a_job_ceiling_rejects_moments_longer_than_it():
    settings = get_settings()
    raw = RawCandidateList(candidates=[candidate(12.0)])

    with pytest.raises(NoValidCandidatesError):
        validate_candidates(raw, settings, video_duration=60.0, max_clip_seconds=10)


def test_the_same_moment_is_kept_under_a_wider_ceiling():
    """The control: only the ceiling differs between this and the test above."""
    settings = get_settings()
    raw = RawCandidateList(candidates=[candidate(12.0)])

    kept = validate_candidates(
        raw, settings, video_duration=60.0, max_clip_seconds=20
    )

    assert [c.duration_seconds for c in kept] == [12.0]


def test_omitting_the_ceiling_falls_back_to_the_server_setting():
    settings = get_settings()
    over_default = settings.teaser_max_seconds + 1
    raw = RawCandidateList(candidates=[candidate(over_default)])

    with pytest.raises(NoValidCandidatesError):
        validate_candidates(raw, settings, video_duration=60.0)


@requires_ffmpeg
def test_one_jobs_options_do_not_leak_into_another(client, uploaded_video):
    """The regression that mutating the cached Settings singleton would cause."""
    video_id = uploaded_video["video_id"]
    settings = get_settings()
    before = (settings.teaser_count, settings.teaser_max_seconds)

    constrained = queue(client, video_id, teaser_count=1, clip_max_seconds=30)
    run(constrained.json()["job_id"], StubProvider(good_candidates()))

    # The process-wide settings are untouched...
    assert (settings.teaser_count, settings.teaser_max_seconds) == before

    # ...so a job that asked for nothing still gets the server default.
    default_job_id = queue(client, video_id).json()["job_id"]
    job = run(default_job_id, StubProvider(good_candidates()))
    assert job.status == "completed", job.error_message

    teasers = client.get(f"/api/videos/{video_id}/teasers").json()["teasers"]
    assert len(teasers) == min(settings.teaser_count, 3)
