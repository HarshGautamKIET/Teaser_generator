"""The connect-time address guard.

These tests exercise the boundary at the level it actually operates: a real
socket connection attempt, not a parsed string. That matters, because the whole
point of this guard is that string validation is bypassable -- an SSRF via a
redirect never presents a bad URL to validate.

A local HTTP server stands in for the attacker's host. It is genuinely
listening on loopback, so "the guard blocks it" is a real refused connection
rather than a mocked one.
"""

import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.services import net_guard
from app.services.net_guard import (
    BlockedAddressError,
    guarded_connections,
    is_forbidden_address,
    resolve_public_addresses,
)


@pytest.fixture
def local_server():
    """An HTTP server on loopback that 302s to the cloud metadata endpoint."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(302)
            self.send_header(
                "Location", "http://169.254.169.254/latest/meta-data/"
            )
            self.end_headers()

        def log_message(self, *args):  # keep the suite output clean
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/video.mp4"
    server.shutdown()
    server.server_close()


# ----------------------------------------------------------------------
# The predicate
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "::1", "10.0.0.1", "192.168.0.1", "172.16.0.1",
        "169.254.169.254",   # cloud instance metadata
        "0.0.0.0", "255.255.255.255", "224.0.0.1",
    ],
)
def test_non_public_addresses_are_forbidden(address):
    import ipaddress

    assert is_forbidden_address(ipaddress.ip_address(address))


@pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"])
def test_public_addresses_are_allowed(address):
    import ipaddress

    assert not is_forbidden_address(ipaddress.ip_address(address))


def test_resolution_refuses_a_name_pointing_at_loopback():
    with pytest.raises(BlockedAddressError):
        resolve_public_addresses("localhost", 80)


# ----------------------------------------------------------------------
# The guard itself
# ----------------------------------------------------------------------
def test_connections_are_unrestricted_outside_the_guard(local_server):
    """The patch is process-wide, so it must be inert when not activated.

    This application connects to private addresses constantly -- the database
    is on a private Docker network -- and those must keep working.
    """
    port = int(local_server.rsplit(":", 1)[1].split("/")[0])

    connection = socket.create_connection(("127.0.0.1", port), timeout=5)
    connection.close()


def test_the_guard_blocks_a_private_address(local_server):
    port = int(local_server.rsplit(":", 1)[1].split("/")[0])

    with guarded_connections():
        with pytest.raises(BlockedAddressError):
            socket.create_connection(("127.0.0.1", port), timeout=5)


def test_the_guard_is_lifted_on_exit(local_server):
    port = int(local_server.rsplit(":", 1)[1].split("/")[0])

    with guarded_connections():
        with pytest.raises(BlockedAddressError):
            socket.create_connection(("127.0.0.1", port), timeout=5)

    socket.create_connection(("127.0.0.1", port), timeout=5).close()


def test_the_guard_is_lifted_even_when_the_block_raises():
    try:
        with guarded_connections():
            raise RuntimeError("something failed mid-download")
    except RuntimeError:
        pass

    assert getattr(net_guard._state, "result", None) is None


def test_one_downloads_verdict_does_not_carry_into_the_next():
    """Background tasks reuse pooled threads, so a stale verdict on a
    thread-local would make the next failure report the wrong cause."""
    with guarded_connections() as first:
        with pytest.raises(BlockedAddressError):
            socket.create_connection(("127.0.0.1", 9), timeout=5)
    assert first.blocked

    with guarded_connections() as second:
        pass
    assert not second.blocked
    assert second.reason is None


def test_the_guard_does_not_leak_into_other_threads(local_server):
    """Thread-local by design: a download must not break concurrent requests."""
    port = int(local_server.rsplit(":", 1)[1].split("/")[0])
    outcome = {}

    def connect_from_another_thread():
        try:
            socket.create_connection(("127.0.0.1", port), timeout=5).close()
            outcome["ok"] = True
        except Exception as exc:  # noqa: BLE001
            outcome["ok"] = False
            outcome["error"] = repr(exc)

    with guarded_connections():
        worker = threading.Thread(target=connect_from_another_thread)
        worker.start()
        worker.join(timeout=10)

    assert outcome.get("ok") is True, outcome.get("error")


def test_the_reason_for_a_block_survives_the_block(local_server):
    """yt-dlp swallows the refusal and raises its own error type, so the cause
    has to still be readable after the context manager has exited."""
    port = int(local_server.rsplit(":", 1)[1].split("/")[0])

    with guarded_connections() as guard:
        with pytest.raises(BlockedAddressError):
            socket.create_connection(("127.0.0.1", port), timeout=5)

    assert guard.blocked
    assert "private or reserved" in guard.reason


# ----------------------------------------------------------------------
# The finding this was written for
# ----------------------------------------------------------------------
def test_a_redirect_into_private_space_is_blocked_on_the_second_hop(
    local_server, monkeypatch
):
    """The SSRF the pre-flight URL check could not see.

    The attack is entirely in the 302: the URL the user submits is fine, and
    only the address it redirects to is not. Proving per-hop enforcement means
    the *first* hop has to succeed, so loopback is treated as public for the
    duration -- standing in for the attacker's genuinely public host -- while
    the metadata address stays forbidden.

    Without the guard this test fails by reaching hop two.
    """
    import ipaddress
    import urllib.request

    real = net_guard.is_forbidden_address

    def public_except_metadata(ip):
        if ip == ipaddress.ip_address("127.0.0.1"):
            return False          # pretend the attacker's host is on the internet
        return real(ip)

    monkeypatch.setattr(net_guard, "is_forbidden_address", public_except_metadata)

    with guarded_connections() as guard:
        with pytest.raises(Exception):
            urllib.request.urlopen(local_server, timeout=5)

    # The refusal came from the guard, on the redirect target -- not from the
    # first request failing or from nothing listening at the destination.
    assert guard.reason == "That URL points at a private or reserved address."


def test_the_first_hop_of_that_redirect_really_does_succeed(
    local_server, monkeypatch
):
    """Control for the test above: proves it reaches hop two at all.

    If the first request were failing on its own, the redirect would never be
    followed and the block above would be proving nothing.
    """
    import ipaddress
    import urllib.request

    real = net_guard.is_forbidden_address
    monkeypatch.setattr(
        net_guard,
        "is_forbidden_address",
        lambda ip: False if ip == ipaddress.ip_address("127.0.0.1") else real(ip),
    )

    with guarded_connections() as guard:
        # Redirects suppressed, so the 302 surfaces instead of being followed.
        # urllib reports an unfollowed redirect as an HTTPError, which still
        # carries the status and headers -- that is the evidence wanted here.
        opener = urllib.request.build_opener(_NoRedirects)
        with pytest.raises(urllib.error.HTTPError) as caught:
            opener.open(local_server, timeout=5)

    assert caught.value.code == 302, "hop one did not complete"
    assert caught.value.headers["Location"].startswith("http://169.254.169.254/")
    # Hop one was allowed; only the target of the redirect is forbidden.
    assert not guard.blocked


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
