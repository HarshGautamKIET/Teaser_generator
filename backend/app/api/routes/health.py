"""Health check.

Deliberately more than a constant. The previous version returned {"status":
"ok"} unconditionally, which meant it could not fail: a backend whose database
had gone away, whose storage was read-only, or whose FFmpeg had vanished still
reported itself healthy, and the container healthcheck that watches this
endpoint would never have restarted it.

Each dependency is probed the cheapest way that would actually notice it
missing, because this runs on a timer.
"""

import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.database import unscoped_session
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

OK = "ok"


def _check_database() -> str:
    """Probe the connection without becoming a user.

    Not the request-scoped `get_db`: that dependency is what makes a route
    authenticated, and depending on it here would put the health endpoint behind
    a token -- which the container healthcheck does not have and cannot get.
    `select 1` needs no privileges, so the powerless role is enough.
    """
    try:
        with unscoped_session() as db:
            db.execute(text("select 1"))
    except SQLAlchemyError as exc:
        logger.warning("Health: database unreachable: %s", exc)
        return "unreachable"
    return OK


def _check_storage(settings: Settings) -> str:
    """Both media roots must exist and be writable.

    Writability rather than mere existence: a full or read-only volume is the
    failure that actually happens, and it presents as a directory that is
    plainly there.
    """
    for label, path in (
        ("uploads", settings.upload_path),
        ("generated", settings.generated_path),
    ):
        if not path.is_dir():
            logger.warning("Health: %s directory missing at %s", label, path)
            return f"{label} directory missing"
        if not os.access(path, os.W_OK):
            logger.warning("Health: %s directory not writable at %s", label, path)
            return f"{label} directory not writable"
    return OK


def _check_ffmpeg(settings: Settings) -> str:
    """Resolve both binaries without executing them.

    `ffmpeg -version` would be the thorough check and the wrong one: two process
    spawns every thirty seconds, forever, to confirm something that only changes
    when the image does.
    """
    missing = [
        name
        for name, configured in (
            ("ffmpeg", settings.ffmpeg_path),
            ("ffprobe", settings.ffprobe_path),
        )
        if not (Path(configured).is_file() or shutil.which(configured))
    ]
    if missing:
        logger.warning("Health: %s not found on PATH", " and ".join(missing))
        return f"{' and '.join(missing)} not found"
    return OK


def _check_ai(settings: Settings) -> str:
    """Report configuration only -- never call the provider.

    A live probe would spend quota and add seconds of latency to something on a
    timer. This is informational and does not fail the check: `fake` is a
    supported offline mode, and a missing key already surfaces per-run as
    AI_NOT_CONFIGURED rather than as an outage.
    """
    if settings.ai_provider == "fake":
        return "fake (offline placeholders)"
    if not (settings.gemini_api_key or settings.gemini_api_keys):
        return "no API key configured"
    return OK


@router.get("/health", response_model=HealthResponse)
async def health(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Report whether this instance can actually do its job.

    Unauthenticated by design -- it is what the container healthcheck and any
    external monitor call, and neither holds an access token. Nothing here
    returns row data, so there is nothing to leak.

    Database, storage, and FFmpeg are required: without any one of them a run
    cannot get past its first stage, so a failure here is a 503 and the
    container healthcheck fails with it. The AI provider is reported but not
    gated -- see `_check_ai`.
    """
    checks = {
        "database": _check_database(),
        "storage": _check_storage(settings),
        "ffmpeg": _check_ffmpeg(settings),
        "ai": _check_ai(settings),
    }

    required = ("database", "storage", "ffmpeg")
    healthy = all(checks[name] == OK for name in required)
    if not healthy:
        response.status_code = 503

    return HealthResponse(status=OK if healthy else "error", checks=checks)
