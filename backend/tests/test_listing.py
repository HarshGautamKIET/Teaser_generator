"""The three cross-record listings: videos, runs, and the clip library.

These endpoints are the first in the API that return rows the caller did not
name by id, so what they must prove is not only that they aggregate correctly
but that RLS still bounds them. A listing that leaked one row of someone else's
work would be a worse failure than any fetch-by-id bug, because it needs no
guessed id to trigger.
"""

from tests.conftest import requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run


def complete_a_run(client, video_id, audience="developers", style="promotional"):
    """Queue and execute one job, returning its id."""
    job_id = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": audience, "style": style},
    ).json()["job_id"]
    run(job_id, StubProvider(good_candidates()), user_id=client.user_id)
    return job_id


# ----------------------------------------------------------------------
# Videos
# ----------------------------------------------------------------------
def test_video_listing_is_empty_before_any_upload(client):
    assert client.get("/api/videos").json() == {"videos": []}


@requires_ffmpeg
def test_video_listing_reports_run_and_clip_counts(client, uploaded_video):
    video_id = uploaded_video["video_id"]
    complete_a_run(client, video_id)
    complete_a_run(client, video_id, audience="students", style="informative")

    videos = client.get("/api/videos").json()["videos"]

    assert len(videos) == 1
    assert videos[0]["video_id"] == video_id
    assert videos[0]["filename"] == "webinar.mp4"
    assert videos[0]["job_count"] == 2
    # Both runs cut clips from the same source, so the video's total spans them.
    assert videos[0]["teaser_count"] == len(
        client.get("/api/teasers").json()["teasers"]
    )


@requires_ffmpeg
def test_video_listing_is_newest_first(client, video_bytes):
    for name in ("first.mp4", "second.mp4"):
        client.post("/api/videos/upload", files={"file": (name, video_bytes, "video/mp4")})

    names = [v["filename"] for v in client.get("/api/videos").json()["videos"]]

    assert names == ["second.mp4", "first.mp4"]


@requires_ffmpeg
def test_video_listing_hides_another_users_videos(client, uploaded_video, other_client):
    assert client.get("/api/videos").json()["videos"] != []
    assert other_client.get("/api/videos").json() == {"videos": []}


def test_video_listing_requires_authentication(anonymous_client):
    response = anonymous_client.get("/api/videos")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


# ----------------------------------------------------------------------
# Runs
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_run_listing_carries_source_and_clip_count(client, uploaded_video):
    job_id = complete_a_run(client, uploaded_video["video_id"])

    jobs = client.get("/api/jobs").json()["jobs"]

    assert len(jobs) == 1
    assert jobs[0]["job_id"] == job_id
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["filename"] == "webinar.mp4"
    assert jobs[0]["audience"] == "developers"
    assert jobs[0]["teaser_count"] > 0
    assert jobs[0]["created_at"] and jobs[0]["completed_at"]


@requires_ffmpeg
def test_run_listing_can_be_filtered_to_one_video(client, uploaded_video, video_bytes):
    complete_a_run(client, uploaded_video["video_id"])
    other = client.post(
        "/api/videos/upload", files={"file": ("other.mp4", video_bytes, "video/mp4")}
    ).json()
    complete_a_run(client, other["video_id"])

    everything = client.get("/api/jobs").json()["jobs"]
    filtered = client.get(f"/api/jobs?video_id={other['video_id']}").json()["jobs"]

    assert len(everything) == 2
    assert [job["video_id"] for job in filtered] == [other["video_id"]]


@requires_ffmpeg
def test_run_listing_hides_another_users_runs(client, uploaded_video, other_client):
    complete_a_run(client, uploaded_video["video_id"])

    assert other_client.get("/api/jobs").json() == {"jobs": []}


# ----------------------------------------------------------------------
# Library
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_library_spans_runs_and_names_the_audience_of_each_clip(
    client, uploaded_video
):
    video_id = uploaded_video["video_id"]
    complete_a_run(client, video_id, audience="developers", style="promotional")
    complete_a_run(client, video_id, audience="students", style="informative")

    teasers = client.get("/api/teasers").json()["teasers"]

    # The per-video endpoint answers with one run; the library answers with both.
    single_run = client.get(f"/api/videos/{video_id}/teasers").json()["teasers"]
    assert len(teasers) > len(single_run)
    assert {t["audience"] for t in teasers} == {"developers", "students"}
    assert all(t["filename"] == "webinar.mp4" for t in teasers)
    assert all(t["video_url"] == f"/teasers/{t['id']}/media" for t in teasers)


@requires_ffmpeg
def test_library_hides_another_users_clips(client, uploaded_video, other_client):
    complete_a_run(client, uploaded_video["video_id"])

    assert other_client.get("/api/teasers").json() == {"teasers": []}
