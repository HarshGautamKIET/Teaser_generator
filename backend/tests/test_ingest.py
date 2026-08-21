"""Fetching a source video from a URL.

The download itself is stubbed -- a suite that reached out to YouTube would be
testing YouTube, would be slow, and would fail whenever a site changed its
player. What is exercised for real is everything this application is actually
responsible for: which URLs it agrees to fetch at all, that a fetch failure
lands on the row instead of vanishing, and that a fetched video is otherwise an
ordinary source video.

The URL guard gets the most attention here because it is the security boundary.
Everywhere else the server handles bytes the user already had; this is the one
endpoint that makes the server originate a request to an address of the user's
choosing.
"""

import shutil
from pathlib import Path

import pytest

from app.database import user_session
from app.errors import AppError
from app.models import SourceType, Video, VideoStatus
from app.services import ingest_service
from app.services.downloader import (
    DownloadResult,
    _format_selector,
    _locate_output,
    _resolve_ffmpeg,
    safe_filename,
)
from tests.conftest import OWNER_ID, requires_ffmpeg


# ----------------------------------------------------------------------
# URL validation (SSRF boundary)
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/internal",
        "http://127.0.0.1/admin",
        "http://127.0.0.53/",
        "https://169.254.169.254/latest/meta-data/",   # cloud instance metadata
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://[::1]/",
    ],
)
def test_private_and_loopback_addresses_are_refused(url):
    with pytest.raises(AppError) as caught:
        ingest_service.assert_fetchable(url)

    assert caught.value.code == "INVALID_SOURCE_URL"
    # The message must not confirm what is actually listening there.
    assert "private or reserved" in caught.value.message


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/video.mp4",
        "gopher://example.com/",
        "data:video/mp4;base64,AAAA",
        "javascript:alert(1)",
    ],
)
def test_non_http_schemes_are_refused(url):
    with pytest.raises(AppError) as caught:
        ingest_service.assert_fetchable(url)

    assert caught.value.code == "INVALID_SOURCE_URL"


def test_absurdly_long_urls_are_refused():
    with pytest.raises(AppError):
        ingest_service.assert_fetchable("https://example.com/" + "a" * 3000)


def test_a_url_with_no_host_is_refused():
    with pytest.raises(AppError):
        ingest_service.assert_fetchable("https:///video.mp4")


def test_an_unresolvable_host_is_refused():
    with pytest.raises(AppError) as caught:
        ingest_service.assert_fetchable(
            "https://this-host-does-not-exist.invalid/video.mp4"
        )

    assert "resolve" in caught.value.message.lower()


def test_a_public_url_is_accepted():
    assert (
        ingest_service.assert_fetchable("  https://example.com/talk.mp4  ")
        == "https://example.com/talk.mp4"
    )


# ----------------------------------------------------------------------
# Filenames derived from a hostile remote title
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "title,expected",
    [
        ("My Talk", "My Talk.mp4"),
        ("../../etc/passwd", "passwd.mp4"),
        ("..\\..\\windows\\system32", "system32.mp4"),
        ("a/b/c", "c.mp4"),
        ("", "video.mp4"),
        ("///", "video.mp4"),
        ("rm -rf $HOME; echo pwned", "rm -rf HOME echo pwned.mp4"),
    ],
)
def test_remote_titles_cannot_become_paths(title, expected):
    assert safe_filename(title, ".mp4") == expected


def test_long_titles_are_capped():
    assert len(safe_filename("x" * 500, ".mp4")) <= 124


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://download.blender.org/x/sintel.mp4", "sintel.mp4"),
        ("https://www.youtube.com/watch?v=abc123", "www.youtube.com"),
        ("https://vimeo.com/12345", "vimeo.com"),
        ("https://example.com/", "example.com"),
    ],
)
def test_a_pending_video_is_labelled_from_its_url(url, expected):
    """A fetch can fail before the source reports a title, and the row still
    has to read as something other than a stuck placeholder."""
    assert ingest_service.provisional_label(url) == expected


# ----------------------------------------------------------------------
# Format selection
# ----------------------------------------------------------------------
def test_the_selector_can_fall_back_to_separate_video_and_audio():
    """Regression: the first version accepted only muxed formats.

    YouTube serves video-only and audio-only streams for essentially
    everything, so a selector built from `best[...]` alone matched nothing and
    every YouTube URL failed with "Requested format is not available".
    """
    selector = _format_selector()

    assert "+bestaudio" in selector, "no merged fallback: YouTube URLs will fail"
    # Progressive still leads, so a plain MP4 link needs no remux.
    assert selector.startswith("best[ext=mp4]")


def test_the_selector_does_not_filter_on_filesize():
    """A predicate on a field DASH manifests omit excludes the format outright
    rather than being ignored, which is how every option got ruled out."""
    assert "filesize" not in _format_selector()


def test_a_merged_download_prefers_the_muxed_file_over_its_parts(tmp_path):
    """Interrupted merges leave `<stem>.f137.mp4` beside `<stem>.mp4`."""
    stem = "abc123"
    (tmp_path / f"{stem}.f137.mp4").write_bytes(b"x" * 900)   # video-only part
    (tmp_path / f"{stem}.f140.m4a").write_bytes(b"x" * 100)   # audio-only part
    (tmp_path / f"{stem}.mp4").write_bytes(b"x" * 500)        # the merged result

    found = _locate_output(tmp_path, stem)

    # Chosen by exact stem, not by size -- the video-only part is larger here.
    assert found.name == f"{stem}.mp4"
    assert not (tmp_path / f"{stem}.f137.mp4").exists()
    assert not (tmp_path / f"{stem}.f140.m4a").exists()


def test_partial_downloads_are_never_treated_as_the_result(tmp_path):
    (tmp_path / "abc123.mp4.part").write_bytes(b"x" * 100)

    assert _locate_output(tmp_path, "abc123") is None


def test_a_bare_ffmpeg_command_resolves_to_its_real_path():
    """Regression: yt-dlp reads ffmpeg_location as a path, not a command.

    Passing the app's default of "ffmpeg" made yt-dlp report ffmpeg as missing
    and refuse to merge, while the binary sat on PATH the whole time.
    """
    resolved = _resolve_ffmpeg("ffmpeg")

    if shutil.which("ffmpeg"):
        assert resolved is not None
        assert Path(resolved).is_file(), "must be a real file, not a bare name"
    else:
        assert resolved is None


def test_an_unresolvable_ffmpeg_yields_none_rather_than_a_bad_path():
    """None lets yt-dlp fall back to its own discovery; a wrong path does not."""
    assert _resolve_ffmpeg("definitely-not-a-real-binary-xyz") is None


# ----------------------------------------------------------------------
# The endpoint
# ----------------------------------------------------------------------
def test_from_url_queues_a_fetch(client, monkeypatch):
    from app.api.routes import videos

    queued: list[tuple] = []
    monkeypatch.setattr(
        videos, "fetch_video_in_background", lambda *args: queued.append(args)
    )

    response = client.post(
        "/api/videos/from-url", json={"url": "https://example.com/talk.mp4"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "fetching"
    assert body["source_type"] == "url"
    assert body["source_url"] == "https://example.com/talk.mp4"
    # No media facts are claimed before anything has been downloaded.
    assert body["duration_seconds"] is None
    assert body["size_bytes"] == 0
    assert len(queued) == 1


def test_from_url_rejects_a_private_address_without_creating_a_row(client):
    response = client.post(
        "/api/videos/from-url", json={"url": "http://127.0.0.1/secret.mp4"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SOURCE_URL"
    # The rejection must happen before any row is written.
    assert client.get("/api/videos").json()["videos"] == []


def test_from_url_requires_authentication(anonymous_client):
    response = anonymous_client.post(
        "/api/videos/from-url", json={"url": "https://example.com/talk.mp4"}
    )

    assert response.status_code == 401


def test_a_fetched_video_is_not_visible_to_another_user(client, other_client, monkeypatch):
    from app.api.routes import videos

    monkeypatch.setattr(videos, "fetch_video_in_background", lambda *args: None)
    client.post("/api/videos/from-url", json={"url": "https://example.com/talk.mp4"})

    assert other_client.get("/api/videos").json()["videos"] == []


# ----------------------------------------------------------------------
# The fetch itself
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_a_successful_fetch_becomes_a_ready_video(
    client, monkeypatch, video_bytes, sample_video_path
):
    """A stubbed download of a real MP4 goes through the real probe."""
    from app.api.routes import videos
    from app.services import downloader
    from app.storage import UPLOADS, get_storage

    monkeypatch.setattr(videos, "fetch_video_in_background", lambda *args: None)
    created = client.post(
        "/api/videos/from-url", json={"url": "https://example.com/talk.mp4"}
    ).json()
    video_id = created["video_id"]

    def fake_download(url, destination_dir, key_stem, **kwargs):
        # Write real bytes where the real downloader would have.
        destination_dir.mkdir(parents=True, exist_ok=True)
        (destination_dir / f"{key_stem}.mp4").write_bytes(video_bytes)
        return DownloadResult(
            storage_key=f"{key_stem}.mp4",
            extension=".mp4",
            size_bytes=len(video_bytes),
            filename="Conference Talk.mp4",
            title="Conference Talk",
            content_type="video/mp4",
        )

    monkeypatch.setattr(downloader, "download", fake_download)

    from app.services.job_runner import fetch_video_in_background

    fetch_video_in_background(video_id, OWNER_ID)

    body = client.get(f"/api/videos/{video_id}").json()
    assert body["status"] == "ready"
    assert body["filename"] == "Conference Talk"
    assert body["duration_seconds"] == pytest.approx(8, abs=1)
    assert body["size_bytes"] == len(video_bytes)

    storage = get_storage()
    with user_session(OWNER_ID) as db:
        video = db.get(Video, video_id)
        assert video.source_type == SourceType.URL
        assert storage.exists(UPLOADS, video.storage_key)


def test_a_failed_download_is_recorded_on_the_video(client, monkeypatch):
    from app.api.routes import videos
    from app.services import downloader
    from app.services.downloader import DownloadError

    monkeypatch.setattr(videos, "fetch_video_in_background", lambda *args: None)
    video_id = client.post(
        "/api/videos/from-url", json={"url": "https://example.com/private.mp4"}
    ).json()["video_id"]

    def refuse(*args, **kwargs):
        raise DownloadError("The video is private.")

    monkeypatch.setattr(downloader, "download", refuse)

    from app.services.job_runner import fetch_video_in_background

    fetch_video_in_background(video_id, OWNER_ID)

    body = client.get(f"/api/videos/{video_id}").json()
    assert body["status"] == VideoStatus.FAILED
    assert body["error_message"] == "The video is private."


def test_an_unexpected_download_crash_still_fails_the_video(client, monkeypatch):
    """A bug in the downloader must not leave a row stuck in `fetching` forever."""
    from app.api.routes import videos
    from app.services import downloader

    monkeypatch.setattr(videos, "fetch_video_in_background", lambda *args: None)
    video_id = client.post(
        "/api/videos/from-url", json={"url": "https://example.com/talk.mp4"}
    ).json()["video_id"]

    def explode(*args, **kwargs):
        raise RuntimeError("something unforeseen")

    monkeypatch.setattr(downloader, "download", explode)

    from app.services.job_runner import fetch_video_in_background

    fetch_video_in_background(video_id, OWNER_ID)

    assert client.get(f"/api/videos/{video_id}").json()["status"] == VideoStatus.FAILED


@requires_ffmpeg
def test_generation_is_refused_while_a_video_is_still_fetching(client, monkeypatch):
    from app.api.routes import videos

    monkeypatch.setattr(videos, "fetch_video_in_background", lambda *args: None)
    video_id = client.post(
        "/api/videos/from-url", json={"url": "https://example.com/talk.mp4"}
    ).json()["video_id"]

    response = client.post(
        f"/api/videos/{video_id}/generate",
        json={"audience": "general", "style": "informative"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VIDEO_NOT_READY"
