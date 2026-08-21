"""Storage package.

The only part of the app that knows where bytes physically live. Callers work
in (area, key) terms so the backing store can change without touching them
(ARCHITECTURE.md extension points).
"""

from app.storage.local import (
    GENERATED,
    UPLOADS,
    Storage,
    StorageLimitExceeded,
    get_storage,
)

__all__ = [
    "GENERATED",
    "UPLOADS",
    "Storage",
    "StorageLimitExceeded",
    "get_storage",
]
