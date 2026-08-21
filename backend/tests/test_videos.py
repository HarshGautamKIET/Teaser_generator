import pytest

from tests.conftest import requires_ffmpeg

@requires_ffmpeg
def test_get_video_returns_metadata(client, video_bytes):
    video_id = client.post(
        "/api/videos/upload",
        files={"file": ("talk.mp4", video_bytes, "video/mp4")},
    ).json()["video_id"]

    response = client.get(f"/api/videos/{video_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["video_id"] == video_id
    assert body["filename"] == "talk.mp4"
    assert body["size_bytes"] == len(video_bytes)
    # FFprobe runs at upload time (Block 2).
    assert body["duration_seconds"] == pytest.approx(8.0, abs=0.5)
    assert body["width"] == 640
    assert body["height"] == 360
    assert body["status"] == "ready"


def test_get_unknown_video_returns_error_envelope(client):
    response = client.get("/api/videos/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "VIDEO_NOT_FOUND",
            "message": "No video found with id does-not-exist.",
        }
    }
