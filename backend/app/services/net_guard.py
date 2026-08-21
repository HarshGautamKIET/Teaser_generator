"""Keeping server-initiated fetches on the public internet.

Validating a URL before handing it to a downloader is not enough. Two things
get past a check that only looks at the string the user submitted:

  * **Redirects.** `https://example.com/video` is a fine URL. It is also
    allowed to answer `302 Location: http://169.254.169.254/latest/meta-data/`,
    and the downloader will follow it. The address that gets connected to is
    never the address that was checked.
  * **DNS rebinding.** A name that resolved to a public address during
    validation is free to resolve to a private one a moment later, when the
    connection is actually made.

Both are closed the same way: check at `connect()` rather than at parse time,
because that is the only point where the address being contacted is the address
that will be used. Every HTTP client available here -- urllib, urllib3, and so
`requests` and yt-dlp above them -- reaches the network through
`socket.create_connection`, so that is where the check goes.

Two details matter for correctness:

  * The patch is installed once and gated on a **thread-local** flag. Patching
    globally without that would apply to every thread in the process, and this
    application legitimately connects to private addresses all the time -- the
    database is `db:5432` on a private Docker network. A blanket check would
    break unrelated requests running concurrently with a download.
  * The connection is made to the **address that was verified**, not to the
    hostname again. Re-resolving would reopen the rebinding window it just
    closed. Passing an IP to `create_connection` does not affect TLS: the
    hostname is carried separately as SNI by the layer above.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from contextlib import contextmanager
from collections.abc import Iterator

from app.errors import AppError

logger = logging.getLogger(__name__)


class BlockedAddressError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("BLOCKED_ADDRESS", message, 400)


def is_forbidden_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for any address that is not a normal public internet host.

    `is_global` is the load-bearing check -- it already excludes loopback,
    private ranges, link-local (and with it 169.254.169.254, the cloud metadata
    endpoint that turns an SSRF into stolen instance credentials), multicast and
    reserved space. The rest are named for the reader, and to stay correct if
    that property is ever narrowed.
    """
    return (
        not ip.is_global
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def resolve_public_addresses(host: str, port: int = 0) -> list[tuple]:
    """Resolve `host`, or raise if any address it maps to is not public.

    Rejects on *any* forbidden result rather than filtering them out: a name
    that answers with both a public and a private address is not a name this
    server should be chasing, and picking the public one would just make the
    behaviour depend on resolver ordering.
    """
    try:
        resolved = socket.getaddrinfo(host, port or None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise BlockedAddressError(f"Could not resolve '{host}'.") from None

    usable: list[tuple] = []
    for family, _type, _proto, _canon, sockaddr in resolved:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        address = ipaddress.ip_address(sockaddr[0])
        if is_forbidden_address(address):
            # Deliberately vague: naming the address would turn this into a
            # network scanner for whoever submitted the URL.
            raise BlockedAddressError(
                "That URL points at a private or reserved address."
            )
        usable.append(sockaddr)

    if not usable:
        raise BlockedAddressError(f"No usable address for '{host}'.")
    return usable


# ----------------------------------------------------------------------
# The connect-time guard
# ----------------------------------------------------------------------
_state = threading.local()
_original_create_connection = socket.create_connection
_installed = False
_install_lock = threading.Lock()


class GuardResult:
    """What a guarded block refused, if anything.

    The reason is reported through an object owned by the caller rather than
    left in thread-local storage, because the caller needs it *after* the block
    has exited -- yt-dlp catches the refusal and re-raises its own error type,
    so the cause is only recoverable out here. Thread-locals would work for
    that too, right up until a pooled worker thread ran a second download and
    inherited the first one's verdict.
    """

    __slots__ = ("reason",)

    def __init__(self) -> None:
        self.reason: str | None = None

    @property
    def blocked(self) -> bool:
        return self.reason is not None


def _guarded_create_connection(address, *args, **kwargs):  # noqa: ANN001
    """Stand-in for socket.create_connection, active per-thread."""
    result: GuardResult | None = getattr(_state, "result", None)
    if result is None:
        return _original_create_connection(address, *args, **kwargs)

    host, port = address[0], address[1]
    try:
        verified = resolve_public_addresses(host, port)
    except BlockedAddressError as exc:
        result.reason = exc.message
        logger.warning("Blocked an outbound connection to %r", host)
        raise

    # Connect to what was checked, not to the name again.
    sockaddr = verified[0]
    return _original_create_connection((sockaddr[0], port), *args, **kwargs)


def _install() -> None:
    global _installed
    with _install_lock:
        if not _installed:
            socket.create_connection = _guarded_create_connection
            _installed = True


@contextmanager
def guarded_connections() -> Iterator[GuardResult]:
    """Within this block, this thread may only connect to public addresses.

    Other threads are unaffected, so concurrent database and API traffic on
    private addresses continues to work normally. The yielded result stays
    readable after the block exits.
    """
    _install()
    previous = getattr(_state, "result", None)
    result = GuardResult()
    _state.result = result
    try:
        yield result
    finally:
        _state.result = previous
