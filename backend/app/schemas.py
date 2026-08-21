"""API response models. Shapes follow API_DESIGN.md exactly."""

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain import AspectRatio, Audience, Style
from app.models import Job, Teaser, Video

# Generated teasers are served by an ownership-checked route, not a static
# mount (see api/routes/media.py). The path is relative to the API base.
def teaser_media_path(teaser_id: str) -> str:
    return f"/teasers/{teaser_id}/media"


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
    # Bound matches Settings.max_custom_prompt_chars and the CHECK in
    # migrations/0006, so an oversized value is a 422 rather than an
    # IntegrityError -- and cannot be used to crowd out the real instructions.
    custom_prompt: str | None = Field(default=None, max_length=500)


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
    custom_prompt: str | None = None
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
            custom_prompt=job.custom_prompt,
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

    @classmethod
    def from_model(cls, teaser: Teaser) -> "TeaserResponse":
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
        )


class TeaserListResponse(BaseModel):
    teasers: list[TeaserResponse]

    @classmethod
    def from_models(cls, teasers: list[Teaser]) -> "TeaserListResponse":
        return cls(teasers=[TeaserResponse.from_model(t) for t in teasers])


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
        cls, teaser: Teaser, filename: str, audience: str, style: str
    ) -> "LibraryTeaser":
        return cls(
            **TeaserResponse.from_model(teaser).model_dump(),
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
        cls, rows: Sequence[tuple[Teaser, str, str, str]]
    ) -> "LibraryResponse":
        return cls(teasers=[LibraryTeaser.from_context(*row) for row in rows])
