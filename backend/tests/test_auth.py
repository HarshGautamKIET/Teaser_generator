"""Authentication and per-user isolation.

These are the tests that protect the security model. Everything here would have
passed trivially before Supabase was introduced, and would keep passing if the
RLS policies were dropped tomorrow -- unless the assertions are about behaviour
a real attacker would try. So they are: sign in as one user, ask for another
user's data, and require that it is not there.
"""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError

from app.database import unscoped_session, user_session
from app.models import Job, JobStatus, Video, new_id
from tests.conftest import OTHER_ID, OWNER_ID, requires_ffmpeg


# ----------------------------------------------------------------------
# Unauthenticated access
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/videos/any-id"),
        ("get", "/api/videos/any-id/teasers"),
        ("get", "/api/jobs/any-id"),
        ("get", "/api/teasers/any-id/media"),
        ("post", "/api/videos/any-id/generate"),
    ],
)
def test_protected_routes_reject_anonymous_callers(anonymous_client, method, path):
    response = getattr(anonymous_client, method)(path)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_health_stays_public(anonymous_client):
    """Liveness must not require a token, or orchestrators cannot probe it."""
    assert anonymous_client.get("/api/health").status_code == 200


@pytest.mark.parametrize(
    "header",
    ["", "Bearer", "Bearer ", "Basic abc123", "not-a-scheme token", "Bearer a.b.c"],
)
def test_malformed_authorization_headers_are_rejected(anonymous_client, header):
    response = anonymous_client.get(
        "/api/videos/any-id", headers={"Authorization": header}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


# ----------------------------------------------------------------------
# Cross-user isolation
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_another_users_video_is_not_found(client, other_client, uploaded_video):
    """404, not 403.

    A 403 would confirm the id exists and belongs to somebody. Absence is the
    only answer that leaks nothing.
    """
    response = other_client.get(f"/api/videos/{uploaded_video['video_id']}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIDEO_NOT_FOUND"


@requires_ffmpeg
def test_another_users_teasers_are_not_listed(client, other_client, uploaded_video):
    response = other_client.get(f"/api/videos/{uploaded_video['video_id']}/teasers")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIDEO_NOT_FOUND"


@requires_ffmpeg
def test_another_user_cannot_start_a_job_on_your_video(
    client, other_client, uploaded_video
):
    response = other_client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIDEO_NOT_FOUND"


@requires_ffmpeg
def test_another_users_job_is_not_found(client, other_client, uploaded_video):
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]

    assert client.get(f"/api/jobs/{job_id}").status_code == 200
    assert other_client.get(f"/api/jobs/{job_id}").status_code == 404


@requires_ffmpeg
def test_another_users_teaser_media_is_not_served(client, other_client, uploaded_video):
    """The regression guarding the old unauthenticated StaticFiles mount.

    Teaser media used to be served straight off disk with no notion of who was
    asking, so any teaser id fetched anyone's video.
    """
    from tests.test_generation import StubProvider, good_candidates, run

    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    url = client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"][0]["video_url"]

    assert client.get(f"/api{url}").status_code == 200
    assert other_client.get(f"/api{url}").status_code == 404


# ----------------------------------------------------------------------
# The database-level guarantee
# ----------------------------------------------------------------------
def _insert_video(user_id: str) -> str:
    video_id = new_id()
    with user_session(user_id) as db:
        db.add(
            Video(
                id=video_id,
                user_id=user_id,
                original_filename="x.mp4",
                storage_key=f"{video_id}.mp4",
                extension=".mp4",
                size_bytes=1,
            )
        )
        db.commit()
    return video_id


def test_rls_hides_other_users_rows_at_the_database():
    """Isolation is enforced by Postgres, not only by application filtering."""
    owner_video = _insert_video(OWNER_ID)
    other_video = _insert_video(OTHER_ID)

    with user_session(OWNER_ID) as db:
        visible = set(db.execute(select(Video.id)).scalars())
    assert owner_video in visible
    assert other_video not in visible

    with user_session(OTHER_ID) as db:
        visible = set(db.execute(select(Video.id)).scalars())
    assert other_video in visible
    assert owner_video not in visible


def test_scope_survives_a_commit():
    """The failure mode a one-shot SET LOCAL would have had.

    SET LOCAL is transaction-scoped, and the service layer commits several times
    per job. If scoping were applied once per session, every statement after the
    first commit would run as the unscoped login role.
    """
    _insert_video(OWNER_ID)

    with user_session(OWNER_ID) as db:
        assert db.execute(select(func.count()).select_from(Video)).scalar() == 1
        db.commit()
        # Same assertion, new transaction.
        assert db.execute(select(func.count()).select_from(Video)).scalar() == 1


def test_unscoped_session_can_read_nothing():
    """Fail closed.

    `teaser_app` holds no privileges on app.*, so a session that never assumes
    the authenticated role is refused outright rather than quietly returning
    every user's rows -- which is what connecting as `postgres` (BYPASSRLS)
    would have done.
    """
    _insert_video(OWNER_ID)

    with unscoped_session() as db:
        with pytest.raises(ProgrammingError, match="permission denied"):
            db.execute(text("select count(*) from app.videos")).scalar()


# ----------------------------------------------------------------------
# Startup reconciliation
# ----------------------------------------------------------------------
def test_interrupted_jobs_are_failed_on_startup():
    """A restart mid-job must not leave the frontend polling forever."""
    video_id = _insert_video(OWNER_ID)
    job_id = new_id()

    with user_session(OWNER_ID) as db:
        db.add(
            Job(
                id=job_id,
                user_id=OWNER_ID,
                video_id=video_id,
                audience="developers",
                style="promotional",
                status=JobStatus.ANALYZING,
                progress=25,
                message="Finding strong moments",
            )
        )
        db.commit()

    with unscoped_session() as db:
        swept = db.execute(select(func.app.reconcile_stranded_jobs())).scalar_one()
        db.commit()
    assert swept >= 1

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.FAILED
        assert job.error_code == "INTERRUPTED"
        assert job.completed_at is not None


def test_reconciliation_leaves_finished_jobs_alone():
    video_id = _insert_video(OWNER_ID)
    job_id = new_id()

    with user_session(OWNER_ID) as db:
        db.add(
            Job(
                id=job_id,
                user_id=OWNER_ID,
                video_id=video_id,
                audience="developers",
                style="promotional",
                status=JobStatus.COMPLETED,
                progress=100,
                message="Generated 3 teaser(s)",
            )
        )
        db.commit()

    with unscoped_session() as db:
        db.execute(select(func.app.reconcile_stranded_jobs())).scalar_one()
        db.commit()

    with user_session(OWNER_ID) as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.error_code is None
