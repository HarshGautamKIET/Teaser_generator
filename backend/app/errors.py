"""Application errors and the single API error envelope.

Every failure returned to a client uses the shape defined in API_DESIGN.md:

    {"error": {"code": "INVALID_VIDEO", "message": "..."}}

Stack traces and secrets are never exposed (SECURITY.md).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that are safe to show to the client."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidVideoError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_VIDEO", message, 400)


class VideoTooLargeError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("VIDEO_TOO_LARGE", message, 413)


class NotFoundError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 404)


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("%s: %s", exc.code, exc.message)
        return error_response(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        detail = first.get("msg", "Invalid request.")
        message = f"{field}: {detail}" if field else detail
        return error_response("VALIDATION_ERROR", message, 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return error_response(code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the real cause server-side, return a generic message to the client.
        logger.exception("Unhandled error: %s", exc)
        return error_response(
            "INTERNAL_ERROR", "An unexpected error occurred.", 500
        )
