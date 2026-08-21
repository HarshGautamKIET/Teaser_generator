"""Deterministic offline provider.

Used by tests, and by AI_PROVIDER=fake for rehearsal without network access.
Its output is explicitly labelled so it can never be mistaken for real analysis
(CLAUDE.md: do not fabricate successful AI results).
"""

from app.ai.base import (
    AIError,
    AIProvider,
    AnalysisRequest,
    RawCandidate,
    RawCandidateList,
    RawScores,
)


class FakeProvider(AIProvider):
    """Spreads evenly spaced candidates across the video, with varied scores."""

    @property
    def name(self) -> str:
        return "fake"

    def analyze_video(self, request: AnalysisRequest) -> RawCandidateList:
        if request.video_duration_seconds < request.min_duration_seconds:
            raise AIError("The video is too short to produce any candidate moments.")

        # Aim for the preferred length, but never exceed the hard limits or the
        # video itself.
        length = float(
            min(
                max(request.min_duration_seconds, request.preferred_min_seconds),
                request.max_duration_seconds,
                request.video_duration_seconds,
            )
        )
        usable = request.video_duration_seconds - length

        # A video only just long enough yields exactly one moment.
        count = max(1, request.candidate_count) if usable > 0 else 1
        step = usable / count if count > 1 else 0.0

        candidates = []
        for index in range(count):
            start = round(index * step, 2)
            end = round(min(start + length, request.video_duration_seconds), 2)
            if end - start < request.min_duration_seconds:
                break
            # Descending scores so ranking has something meaningful to order.
            base = max(1.0, 9.5 - index * 0.7)
            candidates.append(
                RawCandidate(
                    start_seconds=start,
                    end_seconds=end,
                    title=f"[FAKE] Moment {index + 1}",
                    hook=(
                        "[FAKE] Placeholder hook for the "
                        f"{request.audience.value} audience."
                    ),
                    reason=(
                        f"[FAKE] Generated offline for {request.style.value} "
                        "style; this is not real AI analysis."
                    ),
                    scores=RawScores(
                        hook=base,
                        audience_relevance=max(1.0, base - 0.2),
                        information_value=max(1.0, base - 0.4),
                        engagement=max(1.0, base - 0.1),
                        self_contained=max(1.0, base - 0.3),
                    ),
                )
            )
        return RawCandidateList(candidates=candidates)
