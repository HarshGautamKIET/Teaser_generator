"""Cutting on a pause rather than through a word.

The model gives timestamps to the second and cannot hear where its own chosen
moment begins, so a clip that is right about *what* to show is routinely a word
or two wrong about where to start. Nothing downstream noticed: every timestamp
was bounds-checked against the video's duration and none was ever checked
against its audio, so "starts mid-syllable" was a valid clip window.

The pauses stand in for a transcript here. Locating them is enough to place a
cut between two words, and it needs nothing that is not already installed.

Two properties carry most of these tests. The ends snap to opposite things --
a clip starts where speech resumes and stops where it pauses -- and either end
may decline to move, because a boundary with no pause near it is one the model
placed inside continuous speech.
"""

import subprocess

import pytest

from app.config import Settings, get_settings
from app.database import user_session
from app.media import Silence, detect_silence
from app.models import Teaser
from app.services.media_service import snap_window
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run
from tests.test_recording_type import queue


def settings_with(**overrides) -> Settings:
    """Settings for reasoning about snapping, differing in named fields only.

    Never mutates get_settings(): it is an lru_cache'd process-wide singleton,
    so one test's preference would become every other test's.

    Clip lengths are restored to production-like values first. The suite pins
    TEASER_MIN/MAX_SECONDS to 2 and 5 so its eight-second fixture can produce
    clips at all, and under those every window below would be rejected for
    length before snapping was ever considered -- which would pass this file
    while testing nothing.
    """
    base = {
        **get_settings().model_dump(),
        "teaser_min_seconds": 20,
        "teaser_max_seconds": 60,
    }
    return Settings(**{**base, **overrides})


def silences(*pairs) -> list[Silence]:
    return [Silence(start_seconds=start, end_seconds=end) for start, end in pairs]


# ----------------------------------------------------------------------
# Which end snaps to what
# ----------------------------------------------------------------------
def test_the_start_moves_to_where_speech_resumes():
    """The end of a silence, not its start: a clip beginning at the top of a
    pause opens on dead air."""
    start, _ = snap_window(
        10.0, 45.0, silences((9.0, 10.4)), settings_with(), 600.0
    )

    assert start == 10.4


def test_the_end_moves_to_where_speech_pauses():
    """The start of a silence, not its end: a clip ending at the bottom of a
    pause has already begun the next sentence."""
    _, end = snap_window(
        10.0, 45.0, silences((44.6, 45.5)), settings_with(), 600.0
    )

    assert end == 44.6


def test_both_ends_snap_to_the_pauses_around_the_moment():
    window = snap_window(
        30.0, 60.0, silences((28.8, 30.3), (59.2, 60.5)), settings_with(), 600.0
    )

    assert window == (30.3, 59.2)


def test_the_two_ends_move_independently():
    """One end having no pause near it must not stop the other from snapping."""
    window = snap_window(
        30.0, 60.0, silences((29.5, 30.4)), settings_with(), 600.0
    )

    assert window == (30.4, 60.0)


# ----------------------------------------------------------------------
# When not to move
# ----------------------------------------------------------------------
def test_a_boundary_with_no_pause_nearby_is_left_alone():
    """Continuous speech. Dragging the cut to a pause six seconds away would
    change which moment the clip is."""
    window = snap_window(
        30.0, 60.0, silences((0.5, 1.0), (200.0, 201.0)), settings_with(), 600.0
    )

    assert window == (30.0, 60.0)


def test_nothing_moves_without_any_silences():
    window = snap_window(30.0, 60.0, [], settings_with(), 600.0)

    assert window == (30.0, 60.0)


def test_snapping_is_disabled_by_a_zero_shift():
    window = snap_window(
        30.0, 60.0, silences((29.8, 30.5)),
        settings_with(teaser_snap_max_shift_seconds=0.0), 600.0,
    )

    assert window == (30.0, 60.0)


def test_a_shift_that_would_break_the_minimum_length_is_refused():
    """The unsnapped window was already valid, so a slightly worse cut point
    beats a clip the next stage rejects."""
    configured = settings_with(teaser_min_seconds=20, teaser_max_seconds=60)

    # Snapping both ends inward would leave 19.4s, below the 20s minimum.
    window = snap_window(
        30.0, 50.0, silences((29.0, 30.3), (49.7, 50.4)), configured, 600.0
    )

    assert window == (30.0, 50.0)


def test_a_shift_that_would_break_the_maximum_length_is_refused():
    configured = settings_with(teaser_min_seconds=20, teaser_max_seconds=60)

    # Snapping outward would leave 60.6s, above the 60s maximum.
    window = snap_window(
        30.0, 89.8, silences((28.5, 29.7), (90.3, 91.0)), configured, 600.0
    )

    assert window == (30.0, 89.8)


def test_the_runs_own_maximum_is_respected_over_the_servers():
    """A job may carry a shorter ceiling than the server default, and snapping
    must not quietly produce a clip that exceeds the one the run asked for."""
    window = snap_window(
        30.0, 59.5, silences((28.4, 29.6), (60.2, 61.0)),
        settings_with(), 600.0, max_clip_seconds=30,
    )

    assert window == (30.0, 59.5)


def test_a_shift_past_the_end_of_the_video_is_refused():
    window = snap_window(
        560.0, 599.8, silences((600.2, 601.0)), settings_with(), 600.0
    )

    assert window == (560.0, 599.8)


# ----------------------------------------------------------------------
# Finding the pauses in a real file
# ----------------------------------------------------------------------
@pytest.fixture
def video_with_gaps(tmp_path, settings):
    """Eight seconds of tone, muted between 2-3s and 5-6s."""
    path = tmp_path / "gaps.mp4"
    subprocess.run(
        [
            settings.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15:duration=8",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
            "-af", "volume=enable='between(t,2,3)+between(t,5,6)':volume=0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(path),
        ],
        check=True, capture_output=True,
    )
    return path


@requires_ffmpeg
def test_detection_finds_the_real_pauses(video_with_gaps, settings):
    found = detect_silence(
        video_with_gaps, 8.0, ffmpeg_path=settings.ffmpeg_path,
        noise_db=-30, min_silence_seconds=0.3,
    )

    assert len(found) == 2
    # Encoder boundaries land within a frame of where the filter was told to
    # mute, so the assertion is tolerant about the exact hundredth.
    assert found[0].start_seconds == pytest.approx(2.0, abs=0.1)
    assert found[0].end_seconds == pytest.approx(3.0, abs=0.1)
    assert found[1].start_seconds == pytest.approx(5.0, abs=0.1)
    assert found[1].end_seconds == pytest.approx(6.0, abs=0.1)


@requires_ffmpeg
def test_a_continuous_tone_has_no_pauses(sample_video_path, settings):
    """The suite's own fixture is an unbroken 440Hz sine, which is the case
    that must produce no snapping rather than spurious boundaries."""
    found = detect_silence(
        sample_video_path, 8.0, ffmpeg_path=settings.ffmpeg_path,
        noise_db=-30, min_silence_seconds=0.3,
    )

    assert found == []


@requires_ffmpeg
def test_detection_of_an_unreadable_file_returns_nothing_rather_than_raising(
    tmp_path, settings
):
    """Snapping improves a cut point; it is not a precondition for having one.
    A run must not fail because the pauses could not be found."""
    broken = tmp_path / "not-a-video.mp4"
    broken.write_bytes(b"nonsense")

    assert detect_silence(broken, 8.0, ffmpeg_path=settings.ffmpeg_path) == []


def test_detection_with_no_ffmpeg_returns_nothing_rather_than_raising(
    sample_video_path,
):
    """The same contract for a missing binary. Whatever is wrong with FFmpeg
    will be wrong again at the cutting stage, which owns that failure -- so
    this must not be the step that reports it, and must not report it as
    something else."""
    assert detect_silence(
        sample_video_path, 8.0, ffmpeg_path="ffmpeg-that-does-not-exist"
    ) == []


# ----------------------------------------------------------------------
# Through the pipeline
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_the_stored_timestamps_are_the_ones_that_were_cut(client, uploaded_video):
    """A row that disagreed with its own clip would make every timestamp in the
    UI a lie, so the teaser records the snapped window rather than the proposed
    one -- and the clip on disk is that long."""
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        for teaser in db.query(Teaser).filter(Teaser.job_id == job_id).all():
            recorded = teaser.end_seconds - teaser.start_seconds
            assert teaser.duration_seconds == pytest.approx(recorded, abs=0.2)


@requires_ffmpeg
def test_an_unreadable_source_still_fails_as_a_generation_error(
    client, uploaded_video, settings, monkeypatch
):
    """Looking for pauses must not change how a broken file is reported.

    Silence detection runs before the cutting stage and probes the source to
    decide whether there is audio at all. That probe raises on a corrupt file,
    which turned a clean TEASER_GENERATION_FAILED into a generic
    INTERNAL_ERROR from a step the run does not depend on.
    """
    from app.storage import UPLOADS, get_storage

    with user_session(OWNER_ID) as db:
        from app.models import Video

        video = db.get(Video, uploaded_video["video_id"])
        get_storage().resolve(UPLOADS, video.storage_key).write_bytes(b"not a video")

    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == "failed"
    assert job.error_code == "TEASER_GENERATION_FAILED"


@requires_ffmpeg
def test_a_run_still_completes_when_snapping_is_switched_off(
    client, uploaded_video, monkeypatch
):
    """The feature is an improvement to an existing path, so the path has to
    survive turning it off."""
    from app.services import generation_service

    monkeypatch.setattr(
        generation_service.media_service, "snap_window",
        lambda start, end, *args, **kwargs: (start, end),
    )
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    assert run(job_id, StubProvider(good_candidates())).status == "completed"
