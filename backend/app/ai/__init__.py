"""AI package.

Gemini lives here and nowhere else. This package never touches FFmpeg, storage
internals, or HTTP concerns (ARCHITECTURE.md boundaries).
"""

from app.ai.base import (
    AIError,
    AIProvider,
    AnalysisRequest,
    RawCandidate,
    RawCandidateList,
    RawScores,
)
from app.ai.provider import get_ai_provider

__all__ = [
    "AIError",
    "AIProvider",
    "AnalysisRequest",
    "RawCandidate",
    "RawCandidateList",
    "RawScores",
    "get_ai_provider",
]
