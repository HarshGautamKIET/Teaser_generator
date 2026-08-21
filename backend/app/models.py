"""Database models: source videos, processing jobs, and generated teasers.

The schema itself is owned by migrations/0001_init.sql, not by these classes --
row level security, grants, and triggers have no ORM equivalent. These mappings
must stay in step with that file.

Every row carries `user_id`. It is not a convenience column: the RLS policies
compare it against auth.uid(), so a row written with the wrong owner is a row
its author can no longer read.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SCHEMA = "app"


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoStatus:
    """Lifecycle of a source video (distinct from job status)."""

    FETCHING = "fetching"  # being pulled from a URL; no bytes on disk yet
    UPLOADED = "uploaded"
    READY = "ready"      # media metadata extracted
    FAILED = "failed"


class SourceType:
    """How a video arrived."""

    UPLOAD = "upload"
    URL = "url"


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # References auth.users(id). as_uuid=False keeps ids as plain strings
    # everywhere above this layer, matching the token subject.
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)

    # Original name is kept for display only; it is never used as a path.
    original_filename: Mapped[str] = mapped_column(String(255))
    # Storage key is derived from the generated id (SECURITY.md).
    storage_key: Mapped[str] = mapped_column(String(512))
    extension: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=VideoStatus.UPLOADED)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # How the video arrived, and from where. `source_url` is NULL for uploads.
    source_type: Mapped[str] = mapped_column(String(16), default=SourceType.UPLOAD)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class JobStatus:
    """Processing lifecycle (API_DESIGN.md)."""

    QUEUED = "queued"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    RANKING = "ranking"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    # Stopped by its owner. Distinct from `failed` on purpose: nothing went
    # wrong, so it must not be counted as a failure or offered a retry that
    # implies one.
    CANCELLED = "cancelled"

    TERMINAL = (COMPLETED, FAILED, CANCELLED)


class Job(Base):
    """One teaser-generation run for a video, audience, and style."""

    __tablename__ = "jobs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{SCHEMA}.videos.id"), index=True
    )

    audience: Mapped[str] = mapped_column(String(32))
    style: Mapped[str] = mapped_column(String(32))

    # NULL means "use the server default". See migrations/0004 and 0005 for why
    # these are nullable rather than carrying a copied-in default.
    teaser_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clip_max_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Free-text direction for this run. NULL when none was given.
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(String(255), default="Queued")

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Recorded so a demo can show which provider produced the moments.
    ai_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    # Maintained by the jobs_touch_updated_at trigger as well, so a write that
    # bypasses the ORM still moves it.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Teaser(Base):
    """A generated teaser clip and the AI metadata that justified it."""

    __tablename__ = "teasers"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{SCHEMA}.jobs.id"), index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{SCHEMA}.videos.id"), index=True
    )

    # Position in the ranked list, 1 = best.
    rank: Mapped[int] = mapped_column(Integer, default=1)

    title: Mapped[str] = mapped_column(String(255))
    hook: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)

    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)

    storage_key: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
