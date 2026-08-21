"""Rotating Gemini API keys when one runs out of quota.

The risk this carries is not that rotation fails to happen -- it is that it
happens for the wrong reason. Every key in the pool would be spent within
seconds on a malformed request if "the call raised" were treated as "the key is
finished", and the eventual error would name quota rather than the actual bug.
So most of what is tested here is what must *not* rotate.
"""

import pytest

from app.ai.base import AIError, AnalysisRequest
from app.ai.keyring import (
    KeyRing,
    NoKeysRemainingError,
    build_keyring,
    is_quota_exhausted,
)


# ----------------------------------------------------------------------
# Recognising exhaustion
# ----------------------------------------------------------------------
class FakeApiError(Exception):
    """Shaped like the google-genai SDK's error: a code plus a message."""

    def __init__(self, message: str, code: int | None = None, status: str = ""):
        super().__init__(message)
        self.code = code
        self.status = status


@pytest.mark.parametrize(
    "error",
    [
        FakeApiError("Too Many Requests", code=429),
        FakeApiError("quota exceeded", status="RESOURCE_EXHAUSTED"),
        Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric"),
        Exception("You exceeded your current quota, please check your plan"),
        Exception("Rate limit reached for model"),
        Exception("Error 429: too many requests"),
    ],
)
def test_quota_errors_are_recognised(error):
    assert is_quota_exhausted(error)


@pytest.mark.parametrize(
    "error",
    [
        FakeApiError("API key not valid", code=400),
        FakeApiError("Permission denied", code=403),
        FakeApiError("Model not found", code=404),
        FakeApiError("Internal server error", code=500),
        Exception("The video could not be processed"),
        Exception("Invalid JSON in response"),
        ValueError("something else entirely"),
        TimeoutError("timed out"),
    ],
)
def test_other_errors_do_not_burn_a_key(error):
    """The important half: a bad request must not retire the whole pool."""
    assert not is_quota_exhausted(error)


# ----------------------------------------------------------------------
# The ring
# ----------------------------------------------------------------------
def test_keys_are_handed_out_in_order():
    ring = KeyRing(["first", "second", "third"])

    assert ring.current() == "first"
    assert ring.retire("first") is True
    assert ring.current() == "second"
    assert ring.retire("second") is True
    assert ring.current() == "third"


def test_retiring_the_last_key_reports_no_more_remain():
    ring = KeyRing(["only"])

    assert ring.retire("only") is False
    assert ring.exhausted
    with pytest.raises(NoKeysRemainingError):
        ring.current()


def test_a_retired_key_is_never_offered_again():
    """Quota windows outlast a request, so retrying costs a call to learn
    something already known."""
    ring = KeyRing(["first", "second"])
    ring.retire("first")

    assert ring.current() == "second"
    assert "first" not in [ring.current()]


def test_retiring_a_key_that_already_moved_on_is_a_no_op():
    """Two threads failing on the same key must retire it once between them,
    not skip a good key each."""
    ring = KeyRing(["first", "second", "third"])

    ring.retire("first")               # thread A
    assert ring.retire("first") is True  # thread B, same key, already rotated
    assert ring.current() == "second"    # not skipped to "third"


def test_duplicate_keys_are_collapsed():
    ring = KeyRing(["same", "same", "other"])

    assert len(ring) == 2


def test_blank_entries_are_dropped():
    ring = KeyRing(["  real  ", "", "   ", "\n"])

    assert len(ring) == 1
    assert ring.current() == "real"


def test_the_position_description_never_leaks_key_material():
    ring = KeyRing(["super-secret-key", "another-secret"])

    described = ring.describe()

    assert "secret" not in described
    assert described == "key 1/2"


# ----------------------------------------------------------------------
# Assembling it from settings
# ----------------------------------------------------------------------
def test_the_single_key_alone_still_works():
    ring = build_keyring("solo", "")

    assert len(ring) == 1
    assert ring.current() == "solo"


def test_the_pool_is_used_and_the_single_key_appended():
    ring = build_keyring("primary", "a,b")

    assert len(ring) == 3
    assert ring.current() == "a"


def test_a_single_key_already_in_the_pool_is_not_duplicated():
    ring = build_keyring("a", "a,b")

    assert len(ring) == 2


# ----------------------------------------------------------------------
# The provider's retry loop
# ----------------------------------------------------------------------
def make_request(tmp_path):
    from app.domain import Audience, Style

    return AnalysisRequest(
        video_path=tmp_path / "video.mp4",
        audience=Audience.GENERAL, style=Style.INFORMATIVE,
        candidate_count=3, min_duration_seconds=2, max_duration_seconds=5,
        preferred_min_seconds=2, preferred_max_seconds=5,
        video_duration_seconds=30.0,
    )


def build_provider(keys, behaviour):
    """A GeminiProvider whose single network step is `behaviour(key)`."""
    from app.ai.gemini import GeminiProvider

    provider = GeminiProvider(keyring=KeyRing(keys), model="test-model")
    provider._analyze_with = lambda key, request: behaviour(key)
    return provider


def test_the_next_key_is_used_after_a_quota_error(tmp_path):
    from app.ai.base import RawCandidateList

    tried = []

    def behaviour(key):
        tried.append(key)
        if key == "first":
            raise FakeApiError("quota exceeded", code=429)
        return RawCandidateList(candidates=[])

    provider = build_provider(["first", "second"], behaviour)
    result = provider.analyze_video(make_request(tmp_path))

    assert tried == ["first", "second"]
    assert isinstance(result, RawCandidateList)


def test_a_non_quota_error_is_raised_without_touching_the_next_key(tmp_path):
    tried = []

    def behaviour(key):
        tried.append(key)
        raise AIError("Gemini returned an empty response.")

    provider = build_provider(["first", "second"], behaviour)

    with pytest.raises(AIError, match="empty response"):
        provider.analyze_video(make_request(tmp_path))

    assert tried == ["first"], "a non-quota failure must not spend a second key"


def test_exhausting_every_key_reports_it_plainly(tmp_path):
    def behaviour(key):
        raise FakeApiError("quota exceeded", code=429)

    provider = build_provider(["a", "b", "c"], behaviour)

    with pytest.raises(AIError, match="out of quota"):
        provider.analyze_video(make_request(tmp_path))


def test_the_provider_name_reports_position_without_the_key(tmp_path):
    from app.ai.base import RawCandidateList

    def behaviour(key):
        if key == "first":
            raise FakeApiError("429", code=429)
        return RawCandidateList(candidates=[])

    provider = build_provider(["first", "second"], behaviour)
    provider.analyze_video(make_request(tmp_path))

    assert provider.name == "gemini:test-model (key 2/2)"
    assert "first" not in provider.name and "second" not in provider.name


def test_a_provider_with_no_keys_at_all_says_so():
    from app.ai.gemini import GeminiProvider

    with pytest.raises(AIError, match="GEMINI_API_KEY is not set"):
        GeminiProvider(keyring=KeyRing([]), model="test-model")
