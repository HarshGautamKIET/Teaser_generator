"""Media layer: FFprobe facts, FFmpeg cutting, and teaser length policy."""

import pytest

from app.errors import AppError
from app.media import MediaError, build_filter, cut_clip, output_resolution, probe
from app.services.media_service import validate_clip_window
from tests.conftest import requires_ffmpeg


# ----------------------------------------------------------------------
# Pure functions -- no binaries needed
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "ratio,expected",
    [("9:16", (1080, 1920)), ("16:9", (1920, 1080)), ("1:1", (1080, 1080))],
)
def test_output_resolution(ratio, expected):
    assert output_resolution(ratio) == expected


def test_output_dimensions_are_even():
    for ratio in ("9:16", "16:9", "4:3", "3:2"):
        width, height = output_resolution(ratio)
        assert width % 2 == 0 and height % 2 == 0


def test_invalid_aspect_ratio_is_rejected():
    with pytest.raises(MediaError):
        output_resolution("not-a-ratio")


def test_filter_centre_crops_then_scales():
    assert build_filter("9:16") == (
        "crop=w='min(iw,ih*9/16)':h='min(ih,iw*16/9)'"
        ":x='(iw-ow)/2':y='(ih-oh)/2',scale=1080:1920,setsar=1"
    )


# ----------------------------------------------------------------------
# Teaser length policy (FR-009)
# ----------------------------------------------------------------------
def test_valid_window_passes(settings):
    validate_clip_window(settings, 1.0, 4.0, source_duration=8.0)


@pytest.mark.parametrize(
    "start,end,duration",
    [
        (-1.0, 3.0, 8.0),    # negative start
        (5.0, 5.0, 8.0),     # zero length
        (5.0, 4.0, 8.0),     # end before start
        (1.0, 9.0, 8.0),     # past the end of the video
        (1.0, 1.5, 8.0),     # shorter than the minimum
        (1.0, 7.5, 8.0),     # longer than the maximum
    ],
)
def test_invalid_windows_are_rejected(settings, start, end, duration):
    with pytest.raises(AppError):
        validate_clip_window(settings, start, end, source_duration=duration)


# ----------------------------------------------------------------------
# Real FFprobe / FFmpeg
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_probe_reads_real_media_facts(sample_video_path, settings):
    info = probe(sample_video_path, settings.ffprobe_path)

    assert info.duration_seconds == pytest.approx(8.0, abs=0.5)
    assert (info.width, info.height) == (640, 360)
    assert info.fps == pytest.approx(15.0, abs=0.1)
    assert info.video_codec == "h264"
    assert info.has_audio is True


@requires_ffmpeg
def test_probe_rejects_non_video(tmp_path, settings):
    fake = tmp_path / "notes.mp4"
    fake.write_bytes(b"this is not a video")

    with pytest.raises(MediaError):
        probe(fake, settings.ffprobe_path)


@requires_ffmpeg
def test_probe_rejects_missing_file(tmp_path, settings):
    with pytest.raises(MediaError, match="does not exist"):
        probe(tmp_path / "absent.mp4", settings.ffprobe_path)


@requires_ffmpeg
def test_cut_clip_produces_vertical_teaser(sample_video_path, tmp_path, settings):
    output = tmp_path / "teasers" / "teaser_1.mp4"

    result = cut_clip(
        source=sample_video_path,
        output=output,
        start_seconds=2.0,
        end_seconds=6.0,
        ffmpeg_path=settings.ffmpeg_path,
        ffprobe_path=settings.ffprobe_path,
        aspect_ratio="9:16",
    )

    assert result.path.is_file()
    assert result.size_bytes > 0
    assert (result.info.width, result.info.height) == (1080, 1920)
    assert result.info.duration_seconds == pytest.approx(4.0, abs=0.5)
    assert result.info.video_codec == "h264"
    assert result.info.has_audio is True


@requires_ffmpeg
def test_cut_clip_creates_missing_output_directory(sample_video_path, tmp_path, settings):
    output = tmp_path / "a" / "b" / "c" / "teaser.mp4"

    cut_clip(
        source=sample_video_path, output=output,
        start_seconds=0.0, end_seconds=3.0,
        ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path,
    )

    assert output.is_file()


@requires_ffmpeg
@pytest.mark.parametrize("start,end", [(-1.0, 3.0), (4.0, 4.0), (5.0, 2.0)])
def test_cut_clip_rejects_bad_window(sample_video_path, tmp_path, settings, start, end):
    output = tmp_path / "teaser.mp4"

    with pytest.raises(MediaError):
        cut_clip(
            source=sample_video_path, output=output,
            start_seconds=start, end_seconds=end,
            ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path,
        )
    assert not output.exists()


@requires_ffmpeg
def test_cut_clip_rejects_missing_source(tmp_path, settings):
    with pytest.raises(MediaError, match="missing"):
        cut_clip(
            source=tmp_path / "absent.mp4", output=tmp_path / "out.mp4",
            start_seconds=0.0, end_seconds=2.0,
            ffmpeg_path=settings.ffmpeg_path, ffprobe_path=settings.ffprobe_path,
        )


def test_missing_ffmpeg_binary_reports_clearly(sample_video_path, tmp_path, settings):
    with pytest.raises(MediaError, match="not found"):
        cut_clip(
            source=sample_video_path, output=tmp_path / "out.mp4",
            start_seconds=0.0, end_seconds=2.0,
            ffmpeg_path="ffmpeg-that-does-not-exist",
            ffprobe_path=settings.ffprobe_path,
        )
