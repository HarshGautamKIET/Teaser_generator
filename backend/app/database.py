"""Supabase Postgres persistence.

Every session is scoped to one authenticated user. The engine logs in as
`postgres`, but no query runs with those privileges: each transaction drops to
the `authenticated` role and carries the caller's JWT claims, so the row level
security policies in migrations/0001_init.sql decide what is visible.

Scoping is re-applied on `after_begin` rather than once per session on purpose.
`SET LOCAL` and `set_config(..., is_local => true)` are transaction-scoped, and
the service layer commits several times per job -- a one-shot SET would silently
fall back to `postgres` (which bypasses RLS) after the first commit. Binding to
transaction start means it is re-established every time and, just as important,
is discarded automatically when the transaction ends, so a pooled connection can
never carry one user's identity into another user's request.
"""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)

# The Postgres role the app runs as. Matches the RLS policies' TO clause.
APP_ROLE = "authenticated"


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        future=True,
        # Long-running jobs can leave a pooled connection idle past a server-side
        # timeout; pre-ping trades a cheap round trip for a stale-connection error.
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def _bind_user_scope(session: Session, user_id: str) -> None:
    """Make every transaction on `session` run as `user_id`."""
    claims = json.dumps({"sub": user_id, "role": APP_ROLE})

    @event.listens_for(session, "after_begin")
    def _apply_scope(_session, _transaction, connection) -> None:  # noqa: ANN001
        # SET ROLE takes an identifier, not a parameter; APP_ROLE is a constant.
        connection.exec_driver_sql(f"SET LOCAL ROLE {APP_ROLE}")
        # auth.uid() reads request.jwt.claims. Passed as a bound parameter so a
        # user id can never be interpolated into SQL.
        connection.exec_driver_sql(
            "SELECT set_config('request.jwt.claims', %s, true)", (claims,)
        )


@contextmanager
def user_session(user_id: str) -> Iterator[Session]:
    """A session that can only see and write `user_id`'s rows.

    Used directly by background jobs, which run outside a request and so cannot
    use the FastAPI dependency below.
    """
    session = get_session_factory()()
    _bind_user_scope(session, user_id)
    try:
        yield session
    finally:
        session.close()


@contextmanager
def unscoped_session() -> Iterator[Session]:
    """A session that stays as `teaser_app` and never becomes `authenticated`.

    Deliberately powerless: `teaser_app` holds no privileges on app.* (see
    migrations/0002), so this can read and write nothing. Its only use is
    calling the SECURITY DEFINER routines the role is explicitly granted, which
    is how cross-user maintenance happens without an all-rows connection
    existing anywhere in the application.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_db(user_id: str) -> Iterator[Session]:
    """Request-scoped session for a verified caller.

    Not a FastAPI dependency itself -- see api/deps.py, which resolves the user
    from the access token first.
    """
    with user_session(user_id) as session:
        yield session
