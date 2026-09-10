"""The comparison baselines.

An F1 score alone proves nothing; these are what give it meaning. So the
property that matters most here is not that any baseline is good -- they are
meant to be crude -- but that each one is *deterministic*. A baseline that moved
between runs would turn every prompt-change comparison into noise, and the
comparison is the only reason these exist.
"""

from pathlib import Path

import pytest

from app.evaluation.baselines import (
    BASELINE_CLIP_SECONDS,
    audio_peak_spans,
    keyword_spans,
    random_spans,
    uniform_spans,
)
from tests.conftest import requires_ffmpeg


def _no_overlaps(spans):
    ordered = sorted(spans)
    return all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:]))


# ----------------------------------------------------------------------
# uniform
# ----------------------------------------------------------------------
def test_uniform_returns_the_requested_count():
    assert len(uniform_spans(1800.0, 5)) == 5


def test_uniform_stays_inside_the_video():
    """Both edges. A baseline handicapped by running off the end would make the
    pipeline look better for a reason unrelated to either strategy."""
    for start, end in uniform_spans(600.0, 5):
        assert start >= 0.0
        assert end <= 600.0 + 1e-6


def test_uniform_does_not_overlap_itself():
    assert _no_overlaps(uniform_spans(1800.0, 5))


def test_uniform_is_deterministic():
    assert uniform_spans(1800.0, 5) == uniform_spans(1800.0, 5)


def test_uniform_handles_a_video_shorter_than_one_clip():
    spans = uniform_spans(20.0, 3)

    assert len(spans) == 3
    assert all(end <= 20.0 + 1e-6 for _, end in spans)


def test_uniform_returns_nothing_for_a_zero_count():
    assert uniform_spans(1800.0, 0) == []


# ----------------------------------------------------------------------
# random
# ----------------------------------------------------------------------
def test_random_is_reproducible_across_calls():
    """The floor must not move. A baseline that changed run to run would make
    every comparison against it meaningless."""
    assert random_spans(1800.0, 5) == random_spans(1800.0, 5)


def test_random_with_a_different_seed_differs():
    assert random_spans(1800.0, 5, seed=1) != random_spans(1800.0, 5, seed=2)


def test_random_stays_inside_the_video():
    for start, end in random_spans(600.0, 8):
        assert 0.0 <= start
        assert end <= 600.0 + 1e-6


def test_random_clip_length_matches_the_others():
    """Every baseline cuts the same length, so none is advantaged by shape."""
    for start, end in random_spans(1800.0, 4):
        assert end - start == pytest.approx(BASELINE_CLIP_SECONDS)


# ----------------------------------------------------------------------
# keyword
# ----------------------------------------------------------------------
def _captions(pairs):
    return [(start, start + 5.0, text) for start, text in pairs]


def test_keyword_prefers_the_densest_line():
    captions = _captions([
        (10.0, "and so we were there with them"),
        (400.0, "the migration latency dropped and the migration cost dropped"),
        (800.0, "anyway that is all for now"),
    ])
    spans = keyword_spans(captions, 1000.0, 1)

    assert len(spans) == 1
    start, end = spans[0]
    assert start <= 400.0 <= end


def test_keyword_ignores_stopwords():
    """A line of nothing but common words scores zero and is not selected."""
    captions = _captions([(10.0, "and the that have for not with you this but")])

    assert keyword_spans(captions, 1000.0, 3) == []


def test_keyword_returns_nothing_without_a_transcript():
    """Most sources here have none. Returning fewer spans is the honest answer;
    padding with guesses would put a fabricated baseline in the table."""
    assert keyword_spans([], 1000.0, 3) == []


def test_keyword_spans_do_not_overlap():
    captions = _captions([
        (100.0, "latency latency migration"),
        (105.0, "latency migration migration"),
        (900.0, "latency migration cost"),
    ])

    assert _no_overlaps(keyword_spans(captions, 2000.0, 3))


def test_keyword_is_deterministic():
    captions = _captions([
        (100.0, "alpha beta gamma"),
        (500.0, "alpha beta gamma"),
    ])

    assert keyword_spans(captions, 1000.0, 2) == keyword_spans(captions, 1000.0, 2)


# ----------------------------------------------------------------------
# audio_peak -- the baseline that matters
# ----------------------------------------------------------------------
def test_audio_peak_returns_nothing_when_the_file_is_missing():
    """Never a silent substitution. Quietly falling back to another strategy
    would make the comparison a lie in the direction that flatters the
    pipeline."""
    assert audio_peak_spans(Path("no-such-file.mp4"), 600.0, 3) == []


@requires_ffmpeg
def test_audio_peak_measures_a_real_file(sample_video_path, settings):
    spans = audio_peak_spans(
        sample_video_path, 8.0, 2, settings.ffmpeg_path, window_seconds=2.0
    )

    assert spans
    assert _no_overlaps(spans)
    for start, end in spans:
        assert 0.0 <= start < end <= 8.0 + 1e-6


@requires_ffmpeg
def test_audio_peak_is_deterministic(sample_video_path, settings):
    first = audio_peak_spans(
        sample_video_path, 8.0, 2, settings.ffmpeg_path, window_seconds=2.0
    )
    second = audio_peak_spans(
        sample_video_path, 8.0, 2, settings.ffmpeg_path, window_seconds=2.0
    )

    assert first == second
