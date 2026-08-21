"""Teaser listing and authenticated media delivery.

Generated clips used to be served by a StaticFiles mount, which had no notion of
who was asking: anyone holding (or guessing) a teaser id could fetch anyone's
video. With per-user data that is a cross-account leak, so bytes now go through
a route that resolves the teaser via the caller's own RLS-scoped session -- a
teaser belonging to someone else simply is not found.

The cross-run listing lives here too because it shares the /teasers prefix; the
per-video listing stays on the video it belongs to.
"""

import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.errors import NotFoundError
from app.models import Teaser
from app.schemas import LibraryResponse
from app.services import generation_service
from app.storage import GENERATED, Storage, get_storage

router = APIRouter(prefix="/teasers", tags=["media"])


@router.get("", response_model=LibraryResponse)
async def list_all_teasers(db: Session = Depends(get_db)) -> LibraryResponse:
    """Every clip the caller owns, across all runs, newest first."""
    return LibraryResponse.from_rows(generation_service.list_all_teasers(db))


@router.get("/{teaser_id}/media")
async def get_teaser_media(
    teaser_id: str,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> FileResponse:
    """Stream one teaser's MP4 to its owner."""
    teaser = db.get(Teaser, teaser_id)
    if teaser is None:
        raise NotFoundError("TEASER_NOT_FOUND", f"No teaser found with id {teaser_id}.")

    path = storage.resolve(GENERATED, teaser.storage_key)
    if not path.is_file():
        raise NotFoundError(
            "TEASER_MEDIA_MISSING",
            f"The media file for teaser {teaser_id} is no longer on disk.",
        )

    # Named from the clip's title rather than its id. The id would be a stable
    # handle, but it is an internal record identifier and a downloads folder is
    # not the place to publish one.
    slug = re.sub(r"[^a-z0-9]+", "-", teaser.title.lower()).strip("-")[:60]
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"teaser-{teaser.rank}{f'-{slug}' if slug else ''}.mp4",
    )
