"""A pool of Gemini API keys, advanced when one runs out of quota.

A single key makes a free-tier quota a hard stop for the whole deployment: the
next run fails and keeps failing until the window rolls over. Several keys let
the work continue, but only if exhaustion is recognised for what it is.

That recognition is the whole problem. "Out of quota" and "the request was
wrong" both arrive as exceptions from the SDK, and rotating on the second kind
would burn through every key in the pool re-sending a request that was never
going to succeed. So rotation happens on quota signals only -- a 429, or the
RESOURCE_EXHAUSTED status -- and everything else is raised unchanged.

Keys advance in order and do not go back. A key retired mid-process stays
retired: quota windows are measured in minutes to a day, far longer than a
request, so re-trying an exhausted key would just spend a request to learn what
is already known. Restarting the process resets the pool, which is the intended
way to pick a refreshed key back up.
"""

from __future__ import annotations

import logging
import re
import threading

logger = logging.getLogger(__name__)

# Matched against the string form of whatever the SDK raised. Deliberately
# narrow: anything not clearly about quota must not cost a key.
_QUOTA_SIGNALS = re.compile(
    r"resource_exhausted|quota|rate.?limit|too many requests|\b429\b",
    re.IGNORECASE,
)


def is_quota_exhausted(error: BaseException) -> bool:
    """True when `error` says the current key is out of capacity.

    The google-genai SDK reports this as an exception carrying `code` 429, and
    older or wrapped versions surface it only in the message, so both are
    checked rather than trusting one shape.
    """
    for attribute in ("code", "status_code"):
        if getattr(error, attribute, None) == 429:
            return True

    status = getattr(error, "status", None)
    if isinstance(status, str) and status.upper() == "RESOURCE_EXHAUSTED":
        return True

    return bool(_QUOTA_SIGNALS.search(str(error)))


class NoKeysRemainingError(Exception):
    """Every key in the pool is exhausted."""


class KeyRing:
    """Hands out API keys, advancing past exhausted ones.

    Guarded by a lock because generation jobs run in background threads: two
    jobs hitting the quota at the same moment must retire one key between them,
    not two.
    """

    def __init__(self, keys: list[str]) -> None:
        # Order is preserved (it is the caller's stated preference) while
        # duplicates are dropped, so a key listed twice is not tried twice.
        seen: dict[str, None] = {}
        for key in keys:
            cleaned = key.strip()
            if cleaned:
                seen.setdefault(cleaned, None)
        self._keys = list(seen)
        self._index = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._keys)

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return self._index >= len(self._keys)

    def current(self) -> str:
        """The key to use now."""
        with self._lock:
            if self._index >= len(self._keys):
                raise NoKeysRemainingError(
                    f"All {len(self._keys)} Gemini API keys are out of quota."
                )
            return self._keys[self._index]

    def retire(self, key: str) -> bool:
        """Retire `key` and move to the next. True if another key is available.

        The key being retired is passed in, and ignored if it is not the
        current one: two threads that both failed on the same key would
        otherwise advance the pool twice and skip a perfectly good key in
        between.
        """
        with self._lock:
            if self._index >= len(self._keys):
                return False
            if self._keys[self._index] != key:
                # Another thread already moved past this one.
                return self._index < len(self._keys)

            self._index += 1
            remaining = len(self._keys) - self._index
            logger.warning(
                "Gemini key %d of %d is out of quota; %s",
                self._index, len(self._keys),
                f"switching to key {self._index + 1}" if remaining
                else "no keys remain",
            )
            return remaining > 0

    def describe(self) -> str:
        """Position in the pool, for logs and the job's provider label.

        Never includes key material -- this string reaches the API response.
        """
        with self._lock:
            return f"key {min(self._index + 1, len(self._keys))}/{len(self._keys)}"


def build_keyring(primary: str, pool: str) -> KeyRing:
    """Assemble the ring from the single key and the optional pool setting.

    The single key is appended rather than replaced so a deployment that sets
    only GEMINI_API_KEY keeps working untouched, and one that sets both does
    not silently drop the key it has been using.
    """
    keys = [part for part in pool.split(",")] if pool else []
    keys.append(primary)
    return KeyRing(keys)
