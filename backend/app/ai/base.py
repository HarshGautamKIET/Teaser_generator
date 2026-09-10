"""AI provider interface and the structured shapes Gemini must return.

These models describe what the AI *claims*. Nothing here is trusted -- the
backend validates every field before it reaches FFmpeg (SECURITY.md).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from app.domain import DEFAULT_RECORDING_TYPE, Audience, RecordingType, Style

# Guard rails on untrusted AI strings.
MAX_TITLE_CHARS = 120
MAX_HOOK_CHARS = 240
MAX_REASON_CHARS = 500
MAX_SUMMARY_CHARS = 1500
MAX_KEYWORD_CHARS = 60

# Ceilings on how much narrative one response may carry. A two-hour training
# session has a lot of modules, but a chapter list longer than this is a model
# enumerating sentences rather than sections, and it would be unreadable as a
# contents page either way.
MAX_CHAPTERS = 24
MAX_KEYWORDS = 12


class AIError(Exception):
    """The AI call failed, or returned something unusable.

    Never swallowed into a fake success (CLAUDE.md: do not fabricate results).
    """


class RawScores(BaseModel):
    """Per-dimension scores, nominally 0-10 (AI_DESIGN.md).

    Ranges are deliberately not enforced here: one out-of-range value must not
    invalidate the whole response. The validation step clamps or discards.
    """

    hook: float
    audience_relevance: float
    information_value: float
    engagement: float
    self_contained: float


class RawCandidate(BaseModel):
    """One proposed teaser moment.

    This models the *shape* of the AI response only. Timestamp and length rules
    are enforced per-candidate during validation, so a single bad moment is
    discarded rather than failing the entire batch (AI_DESIGN.md).
    """

    start_seconds: float
    end_seconds: float
    title: str
    hook: str
    reason: str
    scores: RawScores


class RawChapter(BaseModel):
    """One section of the source video.

    Bounds are modelled but not enforced here, exactly as for RawCandidate: a
    chapter that runs past the end of the video is dropped during validation
    rather than invalidating the response it arrived in.
    """

    start_seconds: float
    end_seconds: float
    title: str


class RawCandidateList(BaseModel):
    """Top-level structured response schema handed to Gemini.

    Named for the candidates because those are what the run exists to produce,
    but it carries the whole analysis: the narrative fields describe the source
    as a whole rather than any one moment, and they come back from the same call
    because the model has already watched the entire video to find the moments.
    Asking twice would double the cost of the most expensive step for material
    it has just finished reading.

    All three narrative fields default to empty. They are additional to the
    teasers, not a precondition for them, so a model that returns moments and no
    summary produces a run with clips and no summary -- never a failed run.
    """

    candidates: list[RawCandidate]
    summary: str = ""
    chapters: list[RawChapter] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AnalysisRequest:
    """Everything the provider needs to analyse one video.

    The trailing fields carry defaults so existing construction sites keep
    working; the service layer supplies all of them.
    """

    video_path: Path
    audience: Audience
    style: Style
    candidate_count: int
    min_duration_seconds: int
    max_duration_seconds: int
    preferred_min_seconds: int
    preferred_max_seconds: int
    video_duration_seconds: float
    # Free-text direction for this run, or None. Untrusted: see prompt.py.
    custom_prompt: str | None = None
    # Stated in the prompt so the model aims for what the backend enforces,
    # rather than having its output silently thinned out afterwards.
    min_gap_seconds: int = 0
    min_self_contained: float = 0.0
    # Carried as the type rather than as the guidance strings it selects, so
    # the wording lives in exactly one place (domain.RECORDING_PROFILES).
    recording_type: RecordingType = DEFAULT_RECORDING_TYPE
    # Called with (bytes_sent, bytes_total) while the source is transferred to
    # the provider, if it transfers one at all. Two things depend on it, and
    # both need the same call: the run cannot otherwise report a stage that
    # takes tens of minutes, and it cannot otherwise stop one. **Raising from
    # this callback abandons the analysis**, and the exception is delivered to
    # the caller unchanged -- that is how a cancelled run stops its upload
    # rather than paying for the rest of it.
    on_progress: Callable[[int, int], None] | None = None


MAX_CAPTION_CHARS = 220


class RawCaption(BaseModel):
    """One spoken line, timed from the start of the clip it belongs to.

    Clip-relative rather than source-relative because that is what a subtitle
    file needs, and because the model is only ever shown the clip's own audio
    -- it has no way to know where in a two-hour recording that audio came
    from, so asking for absolute times would be inviting it to guess.
    """

    start_seconds: float
    end_seconds: float
    text: str


class RawTranscript(BaseModel):
    """Top-level structured response schema for a transcription call."""

    captions: list[RawCaption] = Field(default_factory=list)


class AIProvider(ABC):
    """A source of candidate teaser moments."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def analyze_video(self, request: AnalysisRequest) -> RawCandidateList:
        """Return proposed moments, or raise AIError. Never returns fake data."""

    def transcribe(self, audio_path: Path, duration_seconds: float) -> RawTranscript:
        """Transcribe one clip's audio into timed lines.

        Concrete rather than abstract, and empty by default, because not every
        provider can do this and captions are an optional output. Making it
        abstract would break every existing implementation -- including the
        stubs in the test suite -- over a capability most of them have no
        reason to have.
        """
        return RawTranscript()
