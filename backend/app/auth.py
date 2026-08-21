"""Supabase authentication.

Access tokens are verified locally against the Auth service's published JWKS.
Self-hosted Supabase signs with an asymmetric ES256 key (see `JWT_KEYS` in
docker/supabase/.env), so verification needs only the public half -- the backend
never holds a signing secret and never calls out to Auth on the request path.

The token is the only thing that establishes identity. `SUPABASE_SECRET_KEY` is
a service-role credential and is deliberately not used here: it bypasses RLS.
"""

import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from jwt import PyJWKClient

from app.config import Settings, get_settings
from app.errors import AppError

logger = logging.getLogger(__name__)

# Supabase mints access tokens with aud="authenticated".
EXPECTED_AUDIENCE = "authenticated"

# Only the asymmetric algorithm is accepted. The self-hosted JWKS also carries a
# legacy symmetric (oct/HS256) entry for older clients; accepting HS256 here
# would mean trusting a shared secret as if it were a public key.
ALLOWED_ALGORITHMS = ["ES256"]


class NotAuthenticatedError(AppError):
    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__("NOT_AUTHENTICATED", message, 401)


@dataclass(frozen=True)
class AuthUser:
    """A verified caller. `id` is the auth.users primary key."""

    id: str
    email: str | None
    role: str


_jwks_client: PyJWKClient | None = None


def get_jwks_client(settings: Settings) -> PyJWKClient:
    """Process-wide JWKS client.

    Keys are cached and only re-fetched when a token presents an unknown `kid`,
    so key rotation is picked up without a restart and without a network call
    per request.
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            settings.supabase_jwks_url,
            cache_keys=True,
            max_cached_keys=8,
        )
    return _jwks_client


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise NotAuthenticatedError("Missing or malformed Authorization header.")
    return token.strip()


def verify_token(token: str, settings: Settings) -> AuthUser:
    """Verify a Supabase access token and return the caller it identifies."""
    try:
        signing_key = get_jwks_client(settings).get_signing_key_from_jwt(token)
    except Exception as exc:
        # Covers an unreachable Auth service as well as an unknown kid; both
        # mean "cannot establish who this is", which is a 401, not a 500.
        logger.warning("Could not resolve a signing key for the token: %s", exc)
        raise NotAuthenticatedError("Could not verify the access token.") from exc

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience=EXPECTED_AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise NotAuthenticatedError("The session has expired. Sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        logger.warning("Rejected an invalid access token: %s", exc)
        raise NotAuthenticatedError("The access token is not valid.") from exc

    subject = claims.get("sub")
    if not subject:
        raise NotAuthenticatedError("The access token has no subject.")

    # `role` decides which Postgres role the request runs as, so an anonymous
    # sign-in must not be mistaken for a real account.
    role = claims.get("role") or ""
    if role != EXPECTED_AUDIENCE:
        raise NotAuthenticatedError(f"Unsupported token role: {role or 'none'}.")

    return AuthUser(id=str(subject), email=claims.get("email"), role=role)


async def get_current_user(
    request: Request, settings: Settings = Depends(get_settings)
) -> AuthUser:
    """FastAPI dependency: the verified caller, or 401."""
    return verify_token(_bearer_token(request), settings)
