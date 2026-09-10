"""The report a real run writes to its own row.

test_pipeline_report.py pins the counting in isolation. These go through the
whole pipeline and the API, because the thing most likely to break is not the
arithmetic but the wiring: a report that is assembled correctly and never
persisted, or persisted and never serialised, looks exactly like no report at
all from the outside.
"""

import pytest

from app.ai.base import RawCandidate, RawCandidateList, RawScores
from app.models import JobStatus
from app.services.pipeline_report import DropReason
from tests.conftest import requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run, scores


def start_run(client, video_id, **body):
    return client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "developers", "style": "promotional", **body},
    ).json()["job_id"]


@requires_ffmpeg
def test_a_completed_run_records_its_report(client, uploaded_video):
    job_id = start_run(client, uploaded_video["video_id"])
    run(job_id, StubProvider(good_candidates()))

    report = client.get(f"/api/jobs/{job_id}").json()["pipeline_report"]

    assert report is not None
    assert report["candidates"]["proposed"] == 3
    assert report["candidates"]["kept"] >= 1


@requires_ffmpeg
def test_the_report_names_what_was_dropped(client, uploaded_video, settings):
    """One candidate past the end of the 8s fixture, one valid."""
    job_id = start_run(client, uploaded_video["video_id"])
    run(job_id, StubProvider([
        RawCandidate(start_seconds=0.0, end_seconds=2.5, title="Good",
                     hook="h", reason="r", scores=scores(9.0)),
        RawCandidate(start_seconds=50.0, end_seconds=54.0, title="Past the end",
                     hook="h", reason="r", scores=scores(9.0)),
    ]))

    report = client.get(f"/api/jobs/{job_id}").json()["pipeline_report"]

    assert report["candidates"]["dropped"][DropReason.BOUNDS] == 1
    assert report["candidates"]["drop_rate"] == pytest.approx(0.5)


@requires_ffmpeg
def test_a_failed_run_still_records_what_it_dropped(client, uploaded_video):
    """The tally of a failed run is the interesting one -- "three proposed,
    three out of bounds" is the entire diagnosis, and recording it only on
    success would lose it exactly when it is needed."""
    job_id = start_run(client, uploaded_video["video_id"])
    job = run(job_id, StubProvider([
        RawCandidate(start_seconds=90.0, end_seconds=94.0, title="Past the end",
                     hook="h", reason="r", scores=scores(9.0)),
    ]))
    assert job.status == JobStatus.FAILED

    report = client.get(f"/api/jobs/{job_id}").json()["pipeline_report"]

    assert report["candidates"]["proposed"] == 1
    assert report["candidates"]["dropped"][DropReason.BOUNDS] == 1
    assert report["candidates"]["kept"] == 0


@requires_ffmpeg
def test_outranked_candidates_appear_in_the_report(client, uploaded_video):
    job_id = start_run(client, uploaded_video["video_id"], teaser_count=1)
    run(job_id, StubProvider(good_candidates()))

    report = client.get(f"/api/jobs/{job_id}").json()["pipeline_report"]

    assert report["candidates"]["kept"] == 1
    assert report["candidates"]["dropped"][DropReason.OUTRANKED] == 2


@requires_ffmpeg
def test_cut_quality_is_measured_for_every_clip(client, uploaded_video, settings):
    """The one quality signal that needs no annotator, no model call and no
    user, so it accumulates whether or not anybody labels anything."""
    if not settings.enable_cut_quality:
        pytest.skip("cut quality measurement is switched off")

    job_id = start_run(client, uploaded_video["video_id"])
    run(job_id, StubProvider(good_candidates()))

    body = client.get(f"/api/jobs/{job_id}").json()
    cuts = body["pipeline_report"]["cuts"]

    assert len(cuts) == len(client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"])
    for cut in cuts:
        assert cut["delta_db"] == pytest.approx(cut["opening_db"] - cut["clip_db"], abs=0.01)


@requires_ffmpeg
def test_a_run_that_produced_fewer_clips_than_asked_says_so(client, uploaded_video):
    job_id = start_run(client, uploaded_video["video_id"], teaser_count=10)
    run(job_id, StubProvider(good_candidates()))

    report = client.get(f"/api/jobs/{job_id}").json()["pipeline_report"]

    assert "fewer_clips_than_requested" in report["degraded"]


@requires_ffmpeg
def test_the_report_appears_in_the_run_history(client, uploaded_video):
    """JobSummary extends JobResponse, so the history table sees it too --
    pinned because the two shapes are easy to let drift apart."""
    job_id = start_run(client, uploaded_video["video_id"])
    run(job_id, StubProvider(good_candidates()))

    jobs = client.get("/api/jobs").json()["jobs"]
    listed = next(j for j in jobs if j["job_id"] == job_id)

    assert listed["pipeline_report"]["candidates"]["proposed"] == 3


@requires_ffmpeg
def test_another_account_cannot_read_the_report(client, other_client, uploaded_video):
    job_id = start_run(client, uploaded_video["video_id"])
    run(job_id, StubProvider(good_candidates()))

    assert other_client.get(f"/api/jobs/{job_id}").status_code == 404
