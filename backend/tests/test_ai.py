"""AI layer: prompt construction, provider contract, and failure behaviour."""

from pathlib import Path

import pytest

from app.ai import AIError, AnalysisRequest, RawCandidateList
from app.ai.fake import FakeProvider
from app.ai.gemini import GeminiProvider
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
def test_gemini_requires_an_api_key():
    with pytest.raises(AIError, match="GEMINI_API_KEY is not set"):
        GeminiProvider(keyring=KeyRing([]), model="gemini-2.5-flash")


def test_gemini_names_itself_with_the_model_and_key_position():
    """The name reaches the API response, so it carries position, not the key."""
    provider = GeminiProvider(keyring=KeyRing(["k1", "k2"]), model="gemini-2.5-flash")

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
