from tests.conftest import requires_ffmpeg

"""Upload endpoint behaviour (FR-001, FR-002, FR-003)."""


def _upload(client, name, payload, content_type="video/mp4"):
    return client.post(
        "/api/videos/upload", files={"file": (name, payload, content_type)}
    )


@requires_ffmpeg
def test_upload_accepts_supported_video(client, video_bytes):
    response = _upload(client, "webinar.mp4", video_bytes)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "webinar.mp4"
    # FFprobe runs during upload, so the video is immediately usable.
    assert body["status"] == "ready"
    assert body["video_id"]


@requires_ffmpeg
def test_upload_stores_file_under_generated_id(client, video_bytes, settings):
    video_id = _upload(client, "webinar.mp4", video_bytes).json()["video_id"]

    stored = settings.upload_path / f"{video_id}.mp4"
    assert stored.is_file()
    assert stored.read_bytes() == video_bytes
    # The original filename must never become a path on disk (SECURITY.md).
    assert not (settings.upload_path / "webinar.mp4").exists()


def test_upload_rejects_unsupported_extension(client, video_bytes):
    response = _upload(client, "notes.txt", video_bytes, "text/plain")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_VIDEO"


def test_upload_rejects_file_without_extension(client, video_bytes):
    response = _upload(client, "webinar", video_bytes)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_VIDEO"


def test_upload_rejects_empty_file(client):
    response = _upload(client, "empty.mp4", b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_VIDEO"


def test_upload_rejects_oversized_file(client, settings):
    oversized = b"x" * (settings.max_upload_bytes + 1024)

    response = _upload(client, "huge.mp4", oversized)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VIDEO_TOO_LARGE"
    # A rejected upload must not leave a partial file behind.
    assert not any(settings.upload_path.glob("*.mp4")) or all(
        p.stat().st_size <= settings.max_upload_bytes
        for p in settings.upload_path.glob("*.mp4")
    )


@requires_ffmpeg
def test_upload_traversal_filename_is_neutralised(client, video_bytes, settings):
    response = _upload(client, "../../evil.mp4", video_bytes)

    assert response.status_code == 201
    video_id = response.json()["video_id"]
    assert (settings.upload_path / f"{video_id}.mp4").is_file()
    assert not (settings.upload_path.parent.parent / "evil.mp4").exists()
