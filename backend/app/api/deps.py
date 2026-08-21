"""Shared route dependencies.

Kept apart from database.py so the persistence layer has no FastAPI import, and
apart from auth.py so token verification stays independently testable.
"""

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user
from app.database import user_session


def get_db(
    user: AuthUser = Depends(get_current_user),
) -> Iterator[Session]:
    """A database session scoped to the verified caller.

    Depending on this dependency is what makes a route authenticated: there is
    no way to obtain a session without first presenting a valid access token.
    """
    with user_session(user.id) as session:
        yield session
