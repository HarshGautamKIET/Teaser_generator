"""AI provider interface and the structured shapes Gemini must return.

These models describe what the AI *claims*. Nothing here is trusted -- the
backend validates every field before it reaches FFmpeg (SECURITY.md).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app.domain import Audience, Style

# Guard rails on untrusted AI strings.
MAX_TITLE_CHARS = 120
MAX_HOOK_CHARS = 240
MAX_REASON_CHARS = 500


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


class RawCandidateList(BaseModel):
    """Top-level structured response schema handed to Gemini."""

    candidates: list[RawCandidate]


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


class AIProvider(ABC):
    """A source of candidate teaser moments."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def analyze_video(self, request: AnalysisRequest) -> RawCandidateList:
        """Return proposed moments, or raise AIError. Never returns fake data."""
