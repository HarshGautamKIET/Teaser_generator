"""Health check.

The point of these tests is that the endpoint can fail. The version they
replaced asserted `{"status": "ok"}` against a function that returned exactly
that and nothing else, so it would have passed just as well with the database
switched off.
"""

import pytest

from app.api.routes import health


def test_health_reports_ok_when_everything_works(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["storage"] == "ok"


def test_health_needs_no_access_token(anonymous_client):
    """The container healthcheck and any external monitor call this without a
    token. Building it on the request-scoped session would put it behind auth
    and leave the container permanently unhealthy on a 401."""
    response = anonymous_client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


def test_health_reports_the_fake_provider(client):
    """The suite forces AI_PROVIDER=fake, and the check should say so rather
    than call it healthy -- a demo silently running on placeholders is exactly
    what this line is for."""
    body = client.get("/api/health").json()

    assert body["checks"]["ai"] == "fake (offline placeholders)"


@pytest.mark.parametrize("broken", ["database", "storage", "ffmpeg"])
def test_a_broken_dependency_is_a_503(client, monkeypatch, broken):
    monkeypatch.setattr(
        health, f"_check_{broken}", lambda *_: "deliberately broken for the test"
    )

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["checks"][broken] == "deliberately broken for the test"


def test_a_broken_ai_provider_is_not_fatal(client, monkeypatch):
    """`fake` is a supported mode and a missing key already surfaces per-run, so
    the AI check is reported without taking the instance out of service."""
    monkeypatch.setattr(health, "_check_ai", lambda *_: "no API key configured")

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["ai"] == "no API key configured"


def test_missing_storage_directory_is_detected(client, monkeypatch, settings, tmp_path):
    """The real probe, not a stubbed one: point storage at a path that is not
    there and confirm the check notices."""
    monkeypatch.setattr(
        type(settings), "upload_path", property(lambda _: tmp_path / "gone")
    )

    response = client.get("/api/health")

    assert response.status_code == 503
    assert "missing" in response.json()["checks"]["storage"]


def test_missing_ffmpeg_is_detected(client, monkeypatch, settings):
    # An instance attribute, unlike upload_path above: ffmpeg_path is a plain
    # settings field, and only the derived paths are class-level properties.
    monkeypatch.setattr(settings, "ffmpeg_path", "definitely-not-a-real-binary-xyz")

    response = client.get("/api/health")

    assert response.status_code == 503
    assert "ffmpeg" in response.json()["checks"]["ffmpeg"]
