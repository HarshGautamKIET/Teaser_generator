"""Local filesystem storage.

Files are addressed by (area, key), never by a caller-supplied path, so the
rest of the app never builds a filesystem path itself. Swapping this for S3
later means implementing the same four methods -- nothing above this layer
knows it is talking to a disk (ADR-007).
"""

import logging
from pathlib import Path
from typing import BinaryIO

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# The two storage areas. Uploads hold untrusted source video; generated holds
# teasers, and is the only one served over HTTP.
UPLOADS = "uploads"
GENERATED = "generated"

CHUNK_BYTES = 1024 * 1024


class StorageLimitExceeded(Exception):
    """The stream was longer than the caller allowed.

    The service layer turns this into the client-facing size error; storage
    itself has no opinion about what the limit should be.
    """


class Storage:
    """Reads and writes files under the configured storage roots."""

    def __init__(self, settings: Settings) -> None:
        self._roots = {
            UPLOADS: settings.upload_path,
            GENERATED: settings.generated_path,
        }

    def root(self, area: str) -> Path:
        try:
            return self._roots[area]
        except KeyError:
            raise ValueError(f"Unknown storage area: {area!r}") from None

    def resolve(self, area: str, key: str) -> Path:
        """Absolute path for a key, guaranteed to stay inside its area.

        Keys are always built from generated ids, but this is enforced rather
        than assumed: a key that escapes its root is a bug or an attack, and
        either way must not reach the filesystem (SECURITY.md).
        """
        root = self.root(area)
        if not key or Path(key).is_absolute():
            raise ValueError(f"Invalid storage key: {key!r}")

        path = (root / key).resolve()
        if path != root.resolve() and not path.is_relative_to(root.resolve()):
            raise ValueError(f"Storage key escapes its area: {key!r}")
        return path

    def exists(self, area: str, key: str) -> bool:
        return self.resolve(area, key).is_file()

    def save_stream(
        self, area: str, key: str, stream: BinaryIO, max_bytes: int
    ) -> int:
        """Write a stream to storage in chunks, returning the bytes written.

        Streaming means an oversized upload is caught partway through instead
        of after the whole file is in memory; the partial file is removed so a
        rejected upload never leaves anything behind (FR-003).
        """
        path = self.resolve(area, key)
        path.parent.mkdir(parents=True, exist_ok=True)

        written = 0
        try:
            with path.open("wb") as destination:
                while chunk := stream.read(CHUNK_BYTES):
                    written += len(chunk)
                    if written > max_bytes:
                        raise StorageLimitExceeded(
                            f"Stream exceeded {max_bytes} bytes."
                        )
                    destination.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise

        return written

    def delete(self, area: str, key: str) -> None:
        """Remove a file if it is there. Absent is not an error."""
        self.resolve(area, key).unlink(missing_ok=True)


_storage: Storage | None = None


def get_storage() -> Storage:
    """The process-wide Storage. Doubles as a FastAPI dependency."""
    global _storage
    if _storage is None:
        settings = get_settings()
        _storage = Storage(settings)
        settings.upload_path.mkdir(parents=True, exist_ok=True)
        settings.generated_path.mkdir(parents=True, exist_ok=True)
    return _storage
