"""AI layer: prompt construction, provider contract, and failure behaviour."""

import io

from pathlib import Path

import pytest

from app.ai import AIError, AnalysisRequest, RawCandidateList
from app.ai.fake import FakeProvider
from app.ai.gemini import CallbackFailed, GeminiProvider, UploadStream
from app.ai.keyring import KeyRing
from app.ai.prompt import build_prompt
from app.domain import Audience, Style


@pytest.fixture
def request_for(settings):
    def _make(audience=Audience.DEVELOPERS, style=Style.PROMOTIONAL, duration=600.0):
        return AnalysisRequest(
            video_path=Path("sample.mp4"),
            audience=audience,
            style=style,
            candidate_count=settings.candidate_count,
            min_duration_seconds=settings.teaser_min_seconds,
            max_duration_seconds=settings.teaser_max_seconds,
            preferred_min_seconds=settings.teaser_preferred_min_seconds,
            preferred_max_seconds=settings.teaser_preferred_max_seconds,
            video_duration_seconds=duration,
        )

    return _make


# ----------------------------------------------------------------------
# Prompt
# ----------------------------------------------------------------------
def test_prompt_carries_audience_and_style(request_for):
    prompt = build_prompt(request_for(Audience.BUSINESS_LEADERS, Style.EMOTIONAL))

    assert "ROI" in prompt                    # business-leader guidance
    assert "storytelling" in prompt           # emotional style guidance
    assert "600.0 seconds long" in prompt


def test_prompt_states_hard_duration_limits(request_for, settings):
    prompt = build_prompt(request_for())

    assert f"at least {settings.teaser_min_seconds} seconds" in prompt
    assert f"most {settings.teaser_max_seconds} seconds" in prompt
    assert "must never exceed 600.0" in prompt


def test_each_audience_produces_distinct_guidance(request_for):
    prompts = {a: build_prompt(request_for(audience=a)) for a in Audience}
    assert len(set(prompts.values())) == len(Audience)


# ----------------------------------------------------------------------
# Provider contract
# ----------------------------------------------------------------------
def test_fake_provider_returns_candidates_in_range(request_for, settings):
    result = FakeProvider().analyze_video(request_for(duration=600.0))

    assert isinstance(result, RawCandidateList)
    assert result.candidates
    for candidate in result.candidates:
        assert 0 <= candidate.start_seconds < candidate.end_seconds <= 600.0
        length = candidate.end_seconds - candidate.start_seconds
        assert settings.teaser_min_seconds <= length <= settings.teaser_max_seconds


def test_fake_provider_output_is_clearly_labelled(request_for):
    result = FakeProvider().analyze_video(request_for())

    # A demo must never mistake offline placeholders for real analysis.
    assert all("[FAKE]" in c.title for c in result.candidates)


def test_fake_provider_fails_on_video_that_is_too_short(request_for):
    with pytest.raises(AIError, match="too short"):
        FakeProvider().analyze_video(request_for(duration=1.0))


# ----------------------------------------------------------------------
# Gemini failure handling -- never fabricate a success
# ----------------------------------------------------------------------
def gemini(keys, model="gemini-2.5-flash"):
    """The provider with its timeouts supplied, as `get_ai_provider` supplies
    them. They carry no default on purpose: the one place they are configured is
    `Settings`, and a second default here could drift out of step with it."""
    return GeminiProvider(
        keyring=KeyRing(keys),
        model=model,
        request_timeout_seconds=300,
        generate_timeout_seconds=900,
    )


def test_gemini_requires_an_api_key():
    with pytest.raises(AIError, match="GEMINI_API_KEY is not set"):
        gemini([])


def test_gemini_names_itself_with_the_model_and_key_position():
    """The name reaches the API response, so it carries position, not the key."""
    provider = gemini(["k1", "k2"])

    assert provider.name == "gemini:gemini-2.5-flash (key 1/2)"
    assert "k1" not in provider.name


class _Response:
    def __init__(self, text=None, parsed=None):
        self.text = text
        self.parsed = parsed


def test_gemini_rejects_empty_response():
    with pytest.raises(AIError, match="empty response"):
        GeminiProvider._parse(_Response(text=""))


def test_gemini_rejects_non_json_response():
    with pytest.raises(AIError, match="not valid JSON"):
        GeminiProvider._parse(_Response(text="I could not analyse this video."))


def test_gemini_rejects_json_that_breaks_the_schema():
    with pytest.raises(AIError, match="did not match the required schema"):
        GeminiProvider._parse(_Response(text='{"candidates": [{"title": "no times"}]}'))


def test_gemini_accepts_valid_json_text():
    payload = """
    {"candidates": [{
        "start_seconds": 10, "end_seconds": 40,
        "title": "A result", "hook": "A hook", "reason": "Because",
        "scores": {"hook": 9, "audience_relevance": 8, "information_value": 7,
                   "engagement": 6, "self_contained": 5}
    }]}
    """
    result = GeminiProvider._parse(_Response(text=payload))

    assert len(result.candidates) == 1
    assert result.candidates[0].title == "A result"


def test_gemini_prefers_the_parsed_structured_object():
    already = RawCandidateList(candidates=[])
    assert GeminiProvider._parse(_Response(text="ignored", parsed=already) ) is already


# ----------------------------------------------------------------------
# Bounding the calls
# ----------------------------------------------------------------------
def test_gemini_bounds_every_request_it_makes():
    """Seconds in, milliseconds out. The SDK's unit is milliseconds, and a
    timeout passed in seconds is a timeout of a third of a second."""
    provider = gemini(["k"])

    assert provider.request_http_options().timeout == 300_000
    assert provider.generate_http_options().timeout == 900_000


# ----------------------------------------------------------------------
# The upload stream: watching a transfer, and abandoning one
# ----------------------------------------------------------------------
def _payload(tmp_path, data=b"0123456789"):
    path = tmp_path / "clip.mp4"
    path.write_bytes(data)
    return path


def test_upload_stream_reports_cumulative_bytes(tmp_path):
    """What the caller needs is how far the transfer has got, not how big the
    last chunk was -- so the count is cumulative and the total comes with it."""
    seen: list[tuple[int, int]] = []

    with UploadStream(_payload(tmp_path), lambda s, t: seen.append((s, t))) as stream:
        while stream.read(4):
            pass

    # The trailing empty read repeats the final position rather than inventing
    # a new one: the callback has to be safe to receive twice.
    assert seen == [(4, 10), (8, 10), (10, 10), (10, 10)]


def test_upload_stream_counts_from_the_rewind_point(tmp_path):
    """The client sizes the file by seeking to the end and back before it reads
    a byte. Counting that seek as progress would report the upload finished
    before it started."""
    seen: list[int] = []

    with UploadStream(_payload(tmp_path), lambda s, t: seen.append(s)) as stream:
        stream.seek(0, io.SEEK_END)
        assert stream.tell() == 10
        stream.seek(0, io.SEEK_SET)
        stream.read(10)

    assert seen == [10]


def test_upload_stream_carries_the_callbacks_failure_out(tmp_path):
    """Raising from the callback is how a cancelled run stops its transfer. The
    reason has to survive the trip out through the SDK -- flattened into a
    generic upload error it would be reported as a Gemini failure."""
    stop = RuntimeError("the run was cancelled")

    def refuse(sent, total):
        raise stop

    with UploadStream(_payload(tmp_path), refuse) as stream:
        with pytest.raises(CallbackFailed) as caught:
            stream.read(4)

    assert caught.value.cause is stop


def test_upload_stream_without_a_callback_still_reads(tmp_path):
    """The callback is optional; the stream is still the thing being uploaded."""
    with UploadStream(_payload(tmp_path), None) as stream:
        assert stream.read(10) == b"0123456789"
