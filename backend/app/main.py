"""FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.config import get_settings
from app.database import unscoped_session
from app.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create storage directories before serving traffic.

    The database schema is not created here. It is owned by
    backend/migrations/*.sql and applied by the `migrate` step in
    docker-compose.yml -- RLS policies, grants, and the dedicated login role have
    no ORM equivalent, so create_all() would produce a subtly different and
    unprotected schema.
    """
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.generated_path.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger(__name__)

    # Processing is in-process, so a restart orphans anything mid-flight. Fail
    # those rows now rather than leave the frontend polling a job whose worker
    # no longer exists. A database that is not reachable yet must not stop the
    # API from booting -- the sweep is housekeeping, not a precondition.
    try:
        with unscoped_session() as db:
            stranded = db.execute(
                select(func.app.reconcile_stranded_jobs())
            ).scalar_one()
            db.commit()
        if stranded:
            log.warning("Marked %d interrupted job(s) as failed on startup", stranded)
    except SQLAlchemyError:
        log.exception("Could not reconcile interrupted jobs on startup")

    log.info(
        "Started. uploads=%s generated=%s",
        settings.upload_path,
        settings.generated_path,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="AI Video Teaser Generator",
        description="Turns long-form video into audience-specific teaser clips.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
