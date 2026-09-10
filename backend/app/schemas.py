"""API response models. Shapes follow API_DESIGN.md exactly."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import AspectRatio, Audience, RecordingType, Style
from app.models import Job, Teaser, TeaserFeedback, Verdict, Video

# Generated teasers are served by an ownership-checked route, not a static
# mount (see api/routes/media.py). The path is relative to the API base.
def teaser_media_path(teaser_id: str) -> str:
    return f"/teasers/{teaser_id}/media"


def preview_media_path(job_id: str) -> str:
    return f"/jobs/{job_id}/preview/media"


class VideoUploadResponse(BaseModel):
    video_id: str
    filename: str
    status: str

    @classmethod
    def from_model(cls, video: Video) -> "VideoUploadResponse":
        return cls(
            video_id=video.id,
            filename=video.original_filename,
            status=video.status,
        )


class VideoResponse(BaseModel):
    video_id: str
    filename: str
    status: str
    size_bytes: int
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    error_message: str | None = None
    source_type: str = "upload"
    source_url: str | None = None

    @classmethod
    def from_model(cls, video: Video) -> "VideoResponse":
        return cls(
            video_id=video.id,
            filename=video.source_title or video.original_filename,
            status=video.status,
            size_bytes=video.size_bytes,
            duration_seconds=video.duration_seconds,
            width=video.width,
            height=video.height,
            fps=video.fps,
            error_message=video.error_message,
            source_type=video.source_type,
            source_url=video.source_url,
        )


class UrlIngestRequest(BaseModel):
    """Body of POST /api/videos/from-url."""

    url: str


class VideoSummary(VideoResponse):
    """A source video as it appears in a listing.

    Extends the detail shape rather than replacing it so the library page and
    the upload flow speak about a video in exactly the same terms.
    """

    created_at: datetime
    job_count: int
    teaser_count: int

    @classmethod
    def from_counts(
        cls, video: Video, job_count: int, teaser_count: int
    ) -> "VideoSummary":
        return cls(
            **VideoResponse.from_model(video).model_dump(),
            created_at=video.created_at,
            job_count=job_count,
            teaser_count=teaser_count,
        )


class VideoListResponse(BaseModel):
    videos: list[VideoSummary]

    @classmethod
    def from_rows(cls, rows: Sequence[tuple[Video, int, int]]) -> "VideoListResponse":
        return cls(videos=[VideoSummary.from_counts(*row) for row in rows])


class HealthResponse(BaseModel):
    status: str
    # Per-dependency detail, so an unhealthy instance says which part is broken
    # rather than only that something is.
    checks: dict[str, str] = {}


class GenerateRequest(BaseModel):
    """Body of POST /api/videos/{video_id}/generate.

    The two pipeline settings are optional: omitted means "use the server
    default", which is what every caller did before they existed. Bounds match
    the CHECK constraints in migrations/0004 so an out-of-range value is a 422
    from the API rather than an IntegrityError from Postgres.
    """

    audience: Audience
    style: Style
    teaser_count: int | None = Field(default=None, ge=1, le=10)
    clip_max_seconds: int | None = Field(default=None, ge=5, le=180)
    aspect_ratio: AspectRatio | None = None
    # Omitted means the default recording type, so a caller written before
    # recording types existed keeps the behaviour it was written against.
    recording_type: RecordingType | None = None
    # Bound matches Settings.max_custom_prompt_chars and the CHECK in
    # migrations/0006, so an oversized value is a 422 rather than an
    # IntegrityError -- and cannot be used to crowd out the real instructions.
    custom_prompt: str | None = Field(default=None, max_length=500)


class ChapterResponse(BaseModel):
    """One section of the source video, as the run described it."""

    start_seconds: float
    end_seconds: float
    title: str


class PipelineReportResponse(BaseModel):
    """What the run discarded, and how cleanly it cut what it kept.

    Deliberately loose. The stored column is an open set of diagnostics that
    grows whenever a check is added to the pipeline, and a strict model here
    would mean two edits and a deploy before a new counter could be seen -- so
    the shape is validated where it is produced (services/pipeline_report.py)
    and passed through here.

    The four named fields are the ones the UI reads; `extra="allow"` keeps
    everything else visible to anyone reading the API directly.
    """

    model_config = ConfigDict(extra="allow")

    candidates: dict[str, Any] = Field(default_factory=dict)
    snap: dict[str, Any] = Field(default_factory=dict)
    cuts: list[dict[str, Any]] = Field(default_factory=list)
    clean_cut_rate: float = 0.0
    degraded: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    video_id: str
    job_id: str
    status: str

    @classmethod
    def from_model(cls, job: Job) -> "GenerateResponse":
        return cls(video_id=job.video_id, job_id=job.id, status=job.status)


class JobResponse(BaseModel):
    job_id: str
    video_id: str
    status: str
    progress: int
    message: str
    audience: str
    style: str
    # None on runs from before the shape was selectable; the client shows the
    # server default rather than inventing one.
    aspect_ratio: str | None = None
    recording_type: str | None = None
    custom_prompt: str | None = None
    # What the run said about the video as a whole. Absent on runs that failed
    # before analysis, and on runs from before this existed -- the client shows
    # nothing rather than an empty section.
    summary: str | None = None
    chapters: list[ChapterResponse] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    # The assembled preview, when the run made one. `preview_url` is present
    # only alongside the rest, so a client can treat it as the single test for
    # whether there is anything to play.
    preview_url: str | None = None
    preview_duration_seconds: float | None = None
    preview_size_bytes: int | None = None
    # What this run threw away and why. None on runs from before the report
    # existed, and on runs that failed before they had anything to report.
    pipeline_report: PipelineReportResponse | None = None
    ai_provider: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def from_model(cls, job: Job) -> "JobResponse":
        return cls(
            job_id=job.id,
            video_id=job.video_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            audience=job.audience,
            style=job.style,
            aspect_ratio=job.aspect_ratio,
            recording_type=job.recording_type,
            custom_prompt=job.custom_prompt,
            summary=job.summary,
            # NULL and [] mean the same thing to a reader, so both become the
            # empty list rather than making every caller handle two absences.
            chapters=[ChapterResponse(**chapter) for chapter in job.chapters or []],
            keywords=job.keywords or [],
            # Requires the caller's access token; storage_key is never exposed.
            preview_url=(
                preview_media_path(job.id) if job.preview_storage_key else None
            ),
            preview_duration_seconds=job.preview_duration_seconds,
            preview_size_bytes=job.preview_size_bytes,
            pipeline_report=(
                PipelineReportResponse(**job.pipeline_report)
                if job.pipeline_report
                else None
            ),
            ai_provider=job.ai_provider,
            error_code=job.error_code,
            error_message=job.error_message,
        )


class JobSummary(JobResponse):
    """A run as it appears in history.

    Carries the timestamps and the source filename that the polling shape has no
    use for but a list of past runs cannot do without.
    """

    filename: str
    teaser_count: int
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_context(cls, job: Job, filename: str, teaser_count: int) -> "JobSummary":
        return cls(
            **JobResponse.from_model(job).model_dump(),
            filename=filename,
            teaser_count=teaser_count,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )


class JobListResponse(BaseModel):
    jobs: list[JobSummary]

    @classmethod
    def from_rows(cls, rows: Sequence[tuple[Job, str, int]]) -> "JobListResponse":
        return cls(jobs=[JobSummary.from_context(*row) for row in rows])


class CaptionResponse(BaseModel):
    """One burned-in caption line, timed from the start of its own clip."""

    start_seconds: float
    end_seconds: float
    text: str


class TeaserResponse(BaseModel):
    id: str
    title: str
    hook: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float | None = None
    score: float
    scores: dict[str, float] = {}
    reason: str
    rank: int
    width: int | None = None
    height: int | None = None
    size_bytes: int
    video_url: str
    # The words burned into the picture, so they can also be read without
    # decoding the clip. Empty when captions were off or nobody spoke.
    captions: list[CaptionResponse] = Field(default_factory=list)
    # The caller's own verdict on this clip, or None if they have not given one.
    # Carried on the clip rather than fetched separately so the control can
    # render in its correct state on first paint instead of flicking from
    # unjudged to judged after a second request.
    feedback: str | None = None

    @classmethod
    def from_model(
        cls, teaser: Teaser, feedback: str | None = None
    ) -> "TeaserResponse":
        return cls(
            id=teaser.id,
            title=teaser.title,
            hook=teaser.hook,
            start_seconds=teaser.start_seconds,
            end_seconds=teaser.end_seconds,
            duration_seconds=teaser.duration_seconds,
            score=teaser.score,
            scores=teaser.scores or {},
            reason=teaser.reason,
            rank=teaser.rank,
            width=teaser.width,
            height=teaser.height,
            size_bytes=teaser.size_bytes,
            # Requires the caller's access token; storage_key is never exposed.
            video_url=teaser_media_path(teaser.id),
            captions=[
                CaptionResponse(**cue) for cue in teaser.captions or []
            ],
            feedback=feedback,
        )


class TeaserListResponse(BaseModel):
    teasers: list[TeaserResponse]

    @classmethod
    def from_models(
        cls, teasers: list[Teaser], verdicts: dict[str, str] | None = None
    ) -> "TeaserListResponse":
        lookup = verdicts or {}
        return cls(
            teasers=[
                TeaserResponse.from_model(t, lookup.get(t.id)) for t in teasers
            ]
        )


class LibraryTeaser(TeaserResponse):
    """A clip in the cross-run library.

    `rank` alone is meaningless once clips from different runs sit side by side,
    so each one states the source and the audience and style it was cut for.
    """

    job_id: str
    video_id: str
    filename: str
    audience: str
    style: str
    created_at: datetime

    @classmethod
    def from_context(
        cls,
        teaser: Teaser,
        filename: str,
        audience: str,
        style: str,
        feedback: str | None = None,
    ) -> "LibraryTeaser":
        return cls(
            **TeaserResponse.from_model(teaser, feedback).model_dump(),
            job_id=teaser.job_id,
            video_id=teaser.video_id,
            filename=filename,
            audience=audience,
            style=style,
            created_at=teaser.created_at,
        )


class LibraryResponse(BaseModel):
    teasers: list[LibraryTeaser]

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[tuple[Teaser, str, str, str]],
        verdicts: dict[str, str] | None = None,
    ) -> "LibraryResponse":
        lookup = verdicts or {}
        return cls(
            teasers=[
                LibraryTeaser.from_context(*row, feedback=lookup.get(row[0].id))
                for row in rows
            ]
        )


# ----------------------------------------------------------------------
# Feedback (docs/EVALUATION.md)
# ----------------------------------------------------------------------
class FeedbackRequest(BaseModel):
    """Body of PUT /api/teasers/{teaser_id}/feedback.

    A Literal rather than the domain enum, because there are exactly two values
    and they are the API's vocabulary as much as the database's. The CHECK in
    migrations/0012 is the same rule stated where a direct write would also hit
    it.
    """

    verdict: Literal["keep", "discard"]
    # Bounded because it is stored and displayed. Long enough for a sentence
    # about why the clip was wrong, which is the only note anyone writes.
    note: str | None = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    teaser_id: str
    verdict: str
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, feedback: TeaserFeedback) -> "FeedbackResponse":
        return cls(
            teaser_id=feedback.teaser_id,
            verdict=feedback.verdict,
            note=feedback.note,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )


class FeedbackSummary(BaseModel):
    """How the caller has judged their clips so far.

    `pending` is the number that matters. A corpus is only worth scoring
    against once most clips have a verdict, and a summary that reported only
    keeps and discards would look complete at three labels out of ninety.
    """

    kept: int = 0
    discarded: int = 0
    pending: int = 0

    @property
    def judged(self) -> int:
        return self.kept + self.discarded

    @classmethod
    def from_counts(
        cls, verdicts: dict[str, int], total_teasers: int
    ) -> "FeedbackSummary":
        kept = verdicts.get(Verdict.KEEP, 0)
        discarded = verdicts.get(Verdict.DISCARD, 0)
        return cls(
            kept=kept,
            discarded=discarded,
            pending=max(0, total_teasers - kept - discarded),
        )
