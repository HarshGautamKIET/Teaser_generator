"""Captions burned into the picture.

Sound-off is the default way a vertical clip gets watched, so a teaser with no
captions is one most of its audience does not hear. The words come from Gemini
transcribing the clip's own audio -- three clips of about a minute each, rather
than the two-hour source the analysis step had to watch, which is the difference
between captions being an option and being the most expensive thing here.

Two things carry these tests. Cue timings are cleaned like every other piece of
model output, because libass renders overlapping cues on top of each other and
never shows one that runs past the end of the clip. And every failure in the
caption path returns no captions rather than costing the run a teaser: the clip
is perfectly good without them.

The styling is checked more literally than it looks. An ASS script states its
own PlayResX/PlayResY, and libass reads every size against that -- which is why
these are written as ASS rather than the more obvious SubRip. An SRT carries no
styling, so it has to be supplied through the filter's `force_style`, and libass
then measures those numbers against a canvas of its own: `Fontsize=44` rendered
at roughly 290 pixels and the text landed across the middle of the frame.
"""

import subprocess

import pytest

from app.ai.base import RawCaption, RawTranscript
from app.ai.fake import FakeProvider
from app.ai.prompt import build_transcription_prompt
from app.database import user_session
from app.media import extract_audio, output_resolution
from app.models import Teaser
from app.services.caption_service import (
    FONT_SIZE,
    MARGIN_V,
    MIN_CUE_SECONDS,
    Caption,
    to_ass,
    validate_captions,
    write_ass,
)
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run
from tests.test_recording_type import queue


def transcript(*cues) -> RawTranscript:
    return RawTranscript(
        captions=[
            RawCaption(start_seconds=start, end_seconds=end, text=text)
            for start, end, text in cues
        ]
    )


class CaptioningProvider(StubProvider):
    """A stub that can also transcribe, which the plain one deliberately cannot."""

    def __init__(self, candidates=None, cues=None, error=None):
        super().__init__(candidates=candidates)
        self._cues = cues
        self._transcribe_error = error
        self.transcribe_calls = 0

    def transcribe(self, audio_path, duration_seconds):
        self.transcribe_calls += 1
        if self._transcribe_error is not None:
            raise self._transcribe_error
        return transcript(*(self._cues or []))


# ----------------------------------------------------------------------
# The default provider cannot transcribe
# ----------------------------------------------------------------------
def test_a_provider_that_cannot_transcribe_returns_nothing_rather_than_failing():
    """transcribe() is concrete and empty on the base class on purpose: making
    it abstract would break every existing implementation over a capability
    most have no reason to have."""
    assert StubProvider().transcribe(None, 30.0) == RawTranscript()


# ----------------------------------------------------------------------
# Cue hygiene
# ----------------------------------------------------------------------
def test_cues_are_normalised_like_every_other_ai_string():
    cues = validate_captions(transcript((0.0, 2.0, "  Hello\x00 there.  ")), 30.0)

    assert [cue.text for cue in cues] == ["Hello there."]


def test_overlapping_cues_are_pulled_apart():
    """libass draws them on top of each other, which is worse than either
    alone. The earlier one is truncated rather than the later one delayed, so a
    cue never appears after the words it captions were spoken."""
    cues = validate_captions(
        transcript((0.0, 3.0, "First"), (1.5, 4.0, "Second")), 30.0
    )

    assert [(c.start_seconds, c.end_seconds) for c in cues] == [(0.0, 1.5), (1.5, 4.0)]


def test_cues_are_returned_in_order_whatever_order_they_arrived_in():
    cues = validate_captions(
        transcript((6.0, 8.0, "Third"), (0.0, 2.0, "First"), (3.0, 5.0, "Second")),
        30.0,
    )

    assert [cue.text for cue in cues] == ["First", "Second", "Third"]


def test_a_cue_running_past_the_end_of_the_clip_is_clamped():
    """It would otherwise never display."""
    cues = validate_captions(transcript((25.0, 999.0, "The end")), 30.0)

    assert cues[0].end_seconds == 30.0


def test_a_cue_entirely_outside_the_clip_is_dropped():
    assert validate_captions(transcript((90.0, 95.0, "Elsewhere")), 30.0) == []


def test_a_flashed_cue_is_extended_rather_than_dropped():
    """The words were spoken. A caption that is hard to read beats one that is
    missing."""
    cues = validate_captions(transcript((5.0, 5.02, "Blink")), 30.0)

    assert cues[0].end_seconds - cues[0].start_seconds == pytest.approx(
        MIN_CUE_SECONDS
    )


def test_an_empty_cue_is_dropped():
    assert validate_captions(transcript((0.0, 2.0, "   ")), 30.0) == []


def test_no_transcript_produces_no_cues():
    assert validate_captions(RawTranscript(), 30.0) == []


# ----------------------------------------------------------------------
# The subtitle script
# ----------------------------------------------------------------------
def test_the_script_declares_the_real_output_resolution():
    """The reason this is ASS. Every size below is measured against these two
    numbers, so they have to be the frame the clip is actually rendered at."""
    width, height = output_resolution("9:16")

    script = to_ass([Caption(0.0, 2.0, "Hello")], width, height)

    assert f"PlayResX: {width}" in script
    assert f"PlayResY: {height}" in script
    assert f",{FONT_SIZE}," in script
    assert f",{MARGIN_V},1" in script


def test_timestamps_use_the_ass_centisecond_form():
    script = to_ass([Caption(61.5, 3723.25, "Hello")], 1080, 1920)

    assert "0:01:01.50,1:02:03.25" in script


def test_braces_are_stripped_from_transcribed_text():
    """Braces are ASS override tags, so text containing one would be read as
    markup and vanish from the picture."""
    script = to_ass([Caption(0.0, 2.0, "Use {braces} carefully")], 1080, 1920)

    assert "Use braces carefully" in script
    assert "{" not in script.split("[Events]")[1]


def test_nothing_is_written_when_there_is_nothing_to_say(tmp_path):
    assert write_ass([], tmp_path / "none.ass", 1080, 1920) is None
    assert not (tmp_path / "none.ass").exists()


def test_the_script_is_written_without_a_byte_order_mark(tmp_path):
    """A BOM would be rendered as a stray glyph at the start of the first cue."""
    path = write_ass([Caption(0.0, 2.0, "Hello")], tmp_path / "c.ass", 1080, 1920)

    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")


# ----------------------------------------------------------------------
# The prompt
# ----------------------------------------------------------------------
def test_the_transcription_prompt_bounds_the_timestamps():
    """The model is given the clip's audio and nothing else, so without the
    duration there is nothing to bound its timestamps against."""
    prompt = build_transcription_prompt(42.5)

    assert "42.5 seconds" in prompt
    assert "not from any" in prompt


# ----------------------------------------------------------------------
# Audio extraction
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_extracted_audio_is_mono_16khz(sample_video_path, tmp_path, settings):
    """What speech recognition wants, and about a twelfth the size of the
    source audio -- this file is about to be sent over the wire."""
    out = extract_audio(
        sample_video_path, tmp_path / "clip.wav", 1.0, 5.0,
        ffmpeg_path=settings.ffmpeg_path,
    )
    probed = subprocess.run(
        [
            settings.ffprobe_path, "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=channels,sample_rate",
            "-of", "csv=p=0", str(out),
        ],
        capture_output=True, text=True, check=True,
    )

    # ffprobe emits these in the stream's own field order, not the order they
    # were asked for, so the pair is compared as a set of values.
    assert sorted(probed.stdout.strip().split(",")) == ["1", "16000"]


@requires_ffmpeg
def test_extracting_a_backwards_window_is_refused(sample_video_path, tmp_path, settings):
    from app.media import MediaError

    with pytest.raises(MediaError, match="must be after"):
        extract_audio(
            sample_video_path, tmp_path / "clip.wav", 5.0, 1.0,
            ffmpeg_path=settings.ffmpeg_path,
        )


# ----------------------------------------------------------------------
# The offline provider
# ----------------------------------------------------------------------
def test_the_fake_provider_labels_its_captions():
    """Burned into the picture, an unmarked plausible caption would be the
    hardest part of an offline rehearsal to tell from real output -- and the
    only part a viewer reads directly off the clip."""
    result = FakeProvider().transcribe(None, 30.0)

    assert result.captions
    assert all("[FAKE]" in cue.text for cue in result.captions)


def test_the_fake_providers_captions_survive_validation():
    cues = validate_captions(FakeProvider().transcribe(None, 30.0), 30.0)

    assert cues


# ----------------------------------------------------------------------
# Through the pipeline
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_captions_are_off_by_default(client, uploaded_video, settings):
    """Every clip would otherwise cost an extra model call, silently. Turning
    them on is a deliberate act."""
    assert settings.enable_captions is False

    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    provider = CaptioningProvider(good_candidates(), cues=[(0.0, 2.0, "Hello")])
    run(job_id, provider)

    assert provider.transcribe_calls == 0
    with user_session(OWNER_ID) as db:
        assert all(
            teaser.captions is None
            for teaser in db.query(Teaser).filter(Teaser.job_id == job_id).all()
        )


@requires_ffmpeg
def test_enabling_captions_burns_and_records_them(
    client, uploaded_video, settings, monkeypatch
):
    monkeypatch.setattr(settings, "enable_captions", True)
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    provider = CaptioningProvider(
        good_candidates(), cues=[(0.0, 1.5, "Spoken words here")]
    )

    job = run(job_id, provider)

    assert job.status == "completed"
    assert provider.transcribe_calls > 0
    with user_session(OWNER_ID) as db:
        teasers = db.query(Teaser).filter(Teaser.job_id == job_id).all()
        assert teasers
        assert all(
            teaser.captions == [
                {"start_seconds": 0.0, "end_seconds": 1.5, "text": "Spoken words here"}
            ]
            for teaser in teasers
        )


@requires_ffmpeg
def test_a_transcription_failure_costs_captions_not_the_clip(
    client, uploaded_video, settings, monkeypatch
):
    """The guarantee the whole feature rests on. A clip is perfectly good
    without captions, so nothing in this path may fail a run."""
    from app.ai import AIError

    monkeypatch.setattr(settings, "enable_captions", True)
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    job = run(
        job_id,
        CaptioningProvider(good_candidates(), error=AIError("quota exhausted")),
    )

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        teasers = db.query(Teaser).filter(Teaser.job_id == job_id).all()
        assert teasers
        assert all(teaser.captions is None for teaser in teasers)


@requires_ffmpeg
def test_a_silent_clip_produces_no_captions_and_still_completes(
    client, uploaded_video, settings, monkeypatch
):
    monkeypatch.setattr(settings, "enable_captions", True)
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    job = run(job_id, CaptioningProvider(good_candidates(), cues=[]))

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        assert all(
            teaser.captions is None
            for teaser in db.query(Teaser).filter(Teaser.job_id == job_id).all()
        )


@requires_ffmpeg
def test_burning_captions_produces_a_larger_clip_than_not(
    client, uploaded_video, settings, monkeypatch
):
    """Proof the text reached the picture rather than only the database.
    Rendered glyphs are detail the encoder has to spend bits on."""
    video_id = uploaded_video["video_id"]
    cues = [(0.0, 2.4, "A caption long enough to cover much of the frame")]

    plain_id = queue(client, video_id).json()["job_id"]
    run(plain_id, CaptioningProvider(good_candidates(), cues=cues))

    monkeypatch.setattr(settings, "enable_captions", True)
    burned_id = queue(client, video_id).json()["job_id"]
    run(burned_id, CaptioningProvider(good_candidates(), cues=cues))

    with user_session(OWNER_ID) as db:
        plain = db.query(Teaser).filter(Teaser.job_id == plain_id).order_by(
            Teaser.rank
        ).first()
        burned = db.query(Teaser).filter(Teaser.job_id == burned_id).order_by(
            Teaser.rank
        ).first()

    assert burned.size_bytes > plain.size_bytes


@requires_ffmpeg
def test_captions_are_reported_back(client, uploaded_video, settings, monkeypatch):
    monkeypatch.setattr(settings, "enable_captions", True)
    video_id = uploaded_video["video_id"]
    job_id = queue(client, video_id).json()["job_id"]
    run(job_id, CaptioningProvider(good_candidates(), cues=[(0.0, 1.5, "Hello")]))

    body = client.get(f"/api/videos/{video_id}/teasers?job_id={job_id}").json()

    assert body["teasers"][0]["captions"] == [
        {"start_seconds": 0.0, "end_seconds": 1.5, "text": "Hello"}
    ]


@requires_ffmpeg
def test_absent_captions_are_reported_as_an_empty_list(client, uploaded_video):
    video_id = uploaded_video["video_id"]
    job_id = queue(client, video_id).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    body = client.get(f"/api/videos/{video_id}/teasers?job_id={job_id}").json()

    assert body["teasers"][0]["captions"] == []
