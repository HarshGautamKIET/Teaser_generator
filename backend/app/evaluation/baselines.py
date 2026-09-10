"""Four other ways to choose spans, so a score means something.

An F1 of 0.6 proves nothing on its own. It is only evidence once you know what
0.6 would have taken without the model, and these are the alternatives:

* `uniform`    -- a clip every N seconds. Costs nothing and is impossible to
                  beat by accident, so any pipeline that loses to it is broken.
* `random`     -- seeded, therefore reproducible. The floor.
* `keyword`    -- windows around the densest occurrences of the video's own
                  frequent content words. A crude "what is this about" heuristic
                  with no model involved.
* `audio_peak` -- the loudest stretches of the audio track.

`audio_peak` is the one that matters, and the reason this module exists. It
approximates what highlight tools did before language models: find where the
speaker got loud or the room reacted, cut there. If Gemini watching the entire
video does not beat measuring volume, then the expensive part of this pipeline
is decorating a heuristic, and that is worth knowing before presenting it as
video understanding.

Everything here is deterministic, `random` included. A baseline that moved
between runs would turn every prompt-change comparison into noise.
"""

import logging
import math
import random
import re
from collections import Counter
from pathlib import Path

from app.media import mean_volume_db

logger = logging.getLogger(__name__)

Span = tuple[float, float]

#: Clip length these baselines produce. Roughly the middle of the product's
#: 20-60s range, so a baseline is not advantaged or handicapped by cutting to a
#: different length than the pipeline it is compared with.
BASELINE_CLIP_SECONDS = 40.0

#: Seeded so `random` is reproducible across runs and machines.
RANDOM_SEED = 42

_WORD = re.compile(r"[a-z][a-z'’-]{2,}")

# Words that are frequent in every transcript and about nothing. A stopword list
# rather than TF-IDF: IDF needs a corpus of other videos, and this baseline is
# meant to be the crude option -- making it clever would understate the gap it
# exists to measure.
_STOPWORDS = frozenset(
    """
    the and that have for not with you this but his from they say her she will
    one all would there their what out about who get which when make can like
    time just him know take people into year your good some could them see other
    than then now look only come its over also back after use two how our work
    first well way even new want because any these give day most are was were
    been has had did does doing more very much such being both each few own same
    too very will can just should now here there where why while
    """.split()
)


def uniform_spans(duration_seconds: float, k: int) -> list[Span]:
    """`k` evenly spaced clips across the whole video.

    The centres are placed at (i + 0.5)/k of the duration rather than at i/k, so
    the first clip does not start at 0:00 and the last does not run off the end
    -- both of which would handicap the baseline for a reason that has nothing
    to do with the strategy.
    """
    if k <= 0 or duration_seconds <= 0:
        return []

    half = min(BASELINE_CLIP_SECONDS, duration_seconds) / 2
    spans = []
    for index in range(k):
        centre = duration_seconds * (index + 0.5) / k
        start = max(0.0, min(centre - half, duration_seconds - 2 * half))
        spans.append((round(start, 3), round(start + 2 * half, 3)))
    return spans


def random_spans(duration_seconds: float, k: int, seed: int = RANDOM_SEED) -> list[Span]:
    """`k` clips at random positions. Seeded, so the floor does not move."""
    if k <= 0 or duration_seconds <= 0:
        return []

    length = min(BASELINE_CLIP_SECONDS, duration_seconds)
    rng = random.Random(seed)
    latest = max(0.0, duration_seconds - length)
    return sorted(
        (round(start, 3), round(start + length, 3))
        for start in (rng.uniform(0.0, latest) for _ in range(k))
    )


def keyword_spans(
    captions: list[tuple[float, float, str]], duration_seconds: float, k: int
) -> list[Span]:
    """Clips centred where the video's own frequent words cluster most densely.

    `captions` is (start, end, text) triples -- whatever transcript is available.
    This project transcribes clips rather than whole videos, so on most sources
    this baseline runs on partial coverage and says so by returning fewer spans
    than asked for, rather than padding with guesses.

    Scores each caption line by how many of the video's top content words it
    contains, then takes the highest-scoring lines that are far enough apart to
    be different moments.
    """
    if k <= 0 or not captions:
        return []

    counts: Counter[str] = Counter()
    for _, _, text in captions:
        counts.update(
            word for word in _WORD.findall(text.lower()) if word not in _STOPWORDS
        )
    if not counts:
        return []

    topic = {word for word, _ in counts.most_common(20)}
    length = min(BASELINE_CLIP_SECONDS, duration_seconds)

    scored = sorted(
        (
            (
                sum(1 for word in _WORD.findall(text.lower()) if word in topic),
                # Earlier wins ties, so the result does not depend on sort
                # stability across Python versions.
                -start,
                start,
            )
            for start, _, text in captions
        ),
        reverse=True,
    )

    spans: list[Span] = []
    for score, _, start in scored:
        if len(spans) >= k or score <= 0:
            break
        centre = start
        begin = max(0.0, min(centre - length / 2, duration_seconds - length))
        candidate = (round(begin, 3), round(begin + length, 3))
        if any(_overlaps(candidate, chosen) for chosen in spans):
            continue
        spans.append(candidate)
    return sorted(spans)


def audio_peak_spans(
    source: Path,
    duration_seconds: float,
    k: int,
    ffmpeg_path: str = "ffmpeg",
    window_seconds: float = BASELINE_CLIP_SECONDS,
) -> list[Span]:
    """The `k` loudest non-overlapping windows of the audio track.

    The baseline that matters: this is what a pre-LLM highlight tool did.

    Measured by stepping a window across the video and taking the mean volume of
    each position. Coarse on purpose -- half a window per step, so a two-hour
    source costs about 180 measurements rather than 7200. A finer sweep would
    find a marginally louder peak and would not change which regions of the
    video win, which is the only thing the comparison turns on.

    Returns fewer spans than asked for, or none, when the audio cannot be
    measured. Silently substituting a different strategy would make the
    comparison a lie in exactly the direction that flatters the pipeline.
    """
    if k <= 0 or duration_seconds <= 0:
        return []

    window = min(window_seconds, duration_seconds)
    step = max(window / 2, 1.0)

    measurements: list[tuple[float, float]] = []
    position = 0.0
    while position + window <= duration_seconds + 1e-6:
        level = mean_volume_db(source, position, position + window, ffmpeg_path)
        if level is not None and math.isfinite(level):
            measurements.append((level, position))
        position += step

    if not measurements:
        logger.warning("audio_peak baseline could not measure %s", Path(source).name)
        return []

    # Loudest first, earlier position breaking ties.
    measurements.sort(key=lambda item: (-item[0], item[1]))

    spans: list[Span] = []
    for _, start in measurements:
        if len(spans) >= k:
            break
        candidate = (round(start, 3), round(start + window, 3))
        if any(_overlaps(candidate, chosen) for chosen in spans):
            continue
        spans.append(candidate)
    return sorted(spans)


def _overlaps(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]
