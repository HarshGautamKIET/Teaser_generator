"""One assembled preview instead of a set of excerpts.

Every other output is a clip that has to stand alone, cut from a single moment.
That is the right shape for repurposing a talk and the wrong one for answering
"what is this course?" -- three disconnected extracts leave the viewer to
assemble the answer themselves, which is the job the artifact was meant to do.

The preview is the other thing: the opening seconds of several moments, held
together by title cards. The cards are the point rather than decoration. They
supply the context each fragment is missing, which is the same context the
self-containment rules spend their effort insisting individual clips must never
need -- so the preview is the one output allowed to be made of fragments.

It costs no tokens. The moments, their titles and the summary were all produced
by the analysis that already ran.
"""

import pytest

from app.database import user_session
from app.media import MediaError, Segment, assemble, output_resolution
from app.models import Job, Teaser
from app.services import preview_service
from app.services.analysis_service import Candidate
from app.services.preview_service import (
    BEAT_SECONDS,
    CLOSING_CARD_SECONDS,
    CLOSING_TEXT,
    FALLBACK_OPENING,
    MAX_BEATS,
    MAX_CARD_CHARS,
    OPENING_CARD_SECONDS,
    headline,
)
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run
from tests.test_recording_type import queue


def candidate(start, end, title="A moment") -> Candidate:
    return Candidate(
        start_seconds=start, end_seconds=end,
        title=title, hook="Worth watching.", reason="For the test.",
    )


def plan_for(*candidates, summary="A session about testing. It goes on.", **kwargs):
    width, height = output_resolution("9:16")
    return preview_service.build(
        list(candidates), "source.mp4", summary, width, height, **kwargs
    )


# ----------------------------------------------------------------------
# The opening line
# ----------------------------------------------------------------------
def test_the_headline_is_the_summarys_first_sentence():
    """A summary is written to be read at leisure; a card is read in two
    seconds."""
    assert headline("A talk about RAG. It also covers evaluation.") == (
        "A talk about RAG."
    )


def test_a_long_first_sentence_is_truncated():
    line = headline("word " * 100)

    assert len(line) <= MAX_CARD_CHARS
    assert line.endswith("…")


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_a_run_without_a_summary_still_gets_a_card(empty):
    """Runs where the model returned moments and nothing else are ordinary, and
    an empty card is worse than a neutral one."""
    assert headline(empty) == FALLBACK_OPENING


# ----------------------------------------------------------------------
# The plan
# ----------------------------------------------------------------------
def test_fewer_than_two_moments_produces_no_preview():
    """One moment is not a preview -- it is the clip that moment already
    produced, with cards bolted on."""
    assert plan_for(candidate(0, 30)) is None
    assert plan_for() is None


def test_a_preview_is_a_card_then_the_beats_then_a_card():
    plan = plan_for(candidate(0, 30), candidate(60, 90), candidate(120, 150))

    assert len(plan.segments) == 5
    assert plan.segments[0].source is None
    assert plan.segments[-1].source is None
    assert all(segment.source is not None for segment in plan.segments[1:-1])


def test_each_beat_starts_where_its_moment_starts():
    plan = plan_for(candidate(12.5, 60), candidate(90, 120))

    assert [s.start_seconds for s in plan.segments[1:-1]] == [12.5, 90.0]


def test_a_beat_is_never_longer_than_the_moment_it_comes_from():
    """A beat that ran past its end would show whatever follows, which was not
    chosen for anything."""
    plan = plan_for(candidate(0, 2.0), candidate(60, 90))

    assert plan.segments[1].duration_seconds == 2.0
    assert plan.segments[2].duration_seconds == BEAT_SECONDS


def test_the_number_of_beats_is_capped():
    """Beyond this it stops being a preview."""
    plan = plan_for(*[candidate(n * 60, n * 60 + 30) for n in range(12)])

    assert len(plan.segments) == MAX_BEATS + 2


def test_the_planned_duration_is_the_sum_of_its_parts():
    plan = plan_for(candidate(0, 30), candidate(60, 90))

    assert plan.duration_seconds == pytest.approx(
        OPENING_CARD_SECONDS + BEAT_SECONDS * 2 + CLOSING_CARD_SECONDS
    )


# ----------------------------------------------------------------------
# The overlay
# ----------------------------------------------------------------------
def test_the_overlay_declares_the_real_output_resolution():
    width, height = output_resolution("9:16")
    plan = plan_for(candidate(0, 30), candidate(60, 90))

    assert f"PlayResX: {width}" in plan.overlay
    assert f"PlayResY: {height}" in plan.overlay


def test_every_moments_title_appears_over_its_own_beat():
    plan = plan_for(
        candidate(0, 30, "First idea"), candidate(60, 90, "Second idea")
    )

    assert "First idea" in plan.overlay
    assert "Second idea" in plan.overlay


def test_titles_are_timed_against_the_assembled_timeline_not_the_source():
    """The beats come from 0s and 60s in the source, but the second title has
    to appear a few seconds into the preview, not a minute in."""
    plan = plan_for(candidate(0, 30, "First"), candidate(60, 90, "Second"))

    # Dialogue lines only -- the style definition is also named "Title".
    events = [
        line for line in plan.overlay.splitlines()
        if line.startswith("Dialogue:") and ",Title," in line
    ]

    assert events[0].startswith(f"Dialogue: 0,0:00:0{int(OPENING_CARD_SECONDS)}")
    assert "0:01:00" not in plan.overlay


def test_the_closing_card_is_last_and_says_so():
    plan = plan_for(candidate(0, 30), candidate(60, 90))

    assert CLOSING_TEXT in plan.overlay.splitlines()[-1]


def test_braces_are_stripped_from_titles():
    """Braces are ASS override tags, so a title containing one would be read as
    markup and vanish."""
    plan = plan_for(candidate(0, 30, "Use {this} carefully"), candidate(60, 90))

    assert "Use this carefully" in plan.overlay
    assert "{" not in plan.overlay.split("[Events]")[1]


# ----------------------------------------------------------------------
# Assembling for real
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_segments_are_joined_into_one_file(sample_video_path, tmp_path, settings):
    segments = [
        Segment(duration_seconds=1.0),
        Segment(duration_seconds=2.0, source=sample_video_path, start_seconds=1.0),
        Segment(duration_seconds=1.0),
    ]

    result = assemble(
        segments, tmp_path / "joined.mp4", 1080, 1920,
        ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path,
    )

    # Frame quantisation moves the total a little either way.
    assert result.info.duration_seconds == pytest.approx(4.0, abs=0.3)
    assert (result.info.width, result.info.height) == (1080, 1920)
    assert result.info.has_audio


@requires_ffmpeg
def test_a_silent_source_still_assembles(sample_video_path, tmp_path, settings):
    """concat refuses streams that disagree, so a source with no audio has to
    be given silence rather than no audio track at all."""
    result = assemble(
        [
            Segment(duration_seconds=1.0),
            Segment(duration_seconds=1.0, source=sample_video_path),
        ],
        tmp_path / "silent.mp4", 720, 720,
        source_has_audio=False,
        ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path,
    )

    assert result.info.has_audio


def test_assembling_nothing_is_refused(tmp_path):
    with pytest.raises(MediaError, match="at least one segment"):
        assemble([], tmp_path / "none.mp4", 1080, 1920)


def test_a_segment_with_no_duration_is_refused(tmp_path):
    with pytest.raises(MediaError, match="non-positive duration"):
        assemble([Segment(duration_seconds=0.0)], tmp_path / "none.mp4", 1080, 1920)


# ----------------------------------------------------------------------
# Through the pipeline
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_a_run_records_its_preview(client, uploaded_video):
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        stored = db.get(Job, job_id)
        assert stored.preview_storage_key
        assert stored.preview_size_bytes > 0
        assert stored.preview_duration_seconds > 0


@requires_ffmpeg
def test_the_preview_is_longer_than_any_one_clip(client, uploaded_video):
    """Proof it was assembled rather than copied: it carries several beats plus
    two cards, so it outlasts the longest moment it was built from."""
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    run(job_id, StubProvider(good_candidates()))

    with user_session(OWNER_ID) as db:
        stored = db.get(Job, job_id)
        longest_clip = max(
            teaser.duration_seconds
            for teaser in db.query(Teaser).filter(Teaser.job_id == job_id).all()
        )

        assert stored.preview_duration_seconds > longest_clip


@requires_ffmpeg
def test_the_preview_is_served_to_its_owner(client, uploaded_video):
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["preview_url"] == f"/jobs/{job_id}/preview/media"

    response = client.get(f"/api/jobs/{job_id}/preview/media")

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert len(response.content) == body["preview_size_bytes"]


@requires_ffmpeg
def test_a_run_without_a_preview_reports_none_and_404s(
    client, uploaded_video, settings, monkeypatch
):
    monkeypatch.setattr(settings, "enable_preview", False)
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    assert client.get(f"/api/jobs/{job_id}").json()["preview_url"] is None

    response = client.get(f"/api/jobs/{job_id}/preview/media")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PREVIEW_NOT_FOUND"


@requires_ffmpeg
def test_a_failed_assembly_costs_the_preview_not_the_run(
    client, uploaded_video, monkeypatch
):
    """The teasers are the run's output; this is an extra artifact built from
    moments that already became clips."""
    from app.services import generation_service

    def explode(*args, **kwargs):
        raise MediaError("no")

    monkeypatch.setattr(generation_service, "assemble", explode)
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        assert db.get(Job, job_id).preview_storage_key is None
