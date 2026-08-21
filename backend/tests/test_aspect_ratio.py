"""Output shape chosen per run.

What matters here is that the chosen ratio reaches FFmpeg and shows up in the
pixels: a value stored on the job but never applied would look correct in every
API response and produce the wrong video.
"""

import pytest

from app.database import user_session
from app.domain import DEFAULT_ASPECT_RATIO, AspectRatio
from app.media import build_filter, output_resolution
from app.models import Job
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run


def queue(client, video_id, **body):
    payload = {"audience": "developers", "style": "promotional", **body}
    return client.post(f"/api/videos/{video_id}/generate", json=payload)


# ----------------------------------------------------------------------
# The vocabulary
# ----------------------------------------------------------------------
def test_widescreen_is_the_default():
    assert DEFAULT_ASPECT_RATIO is AspectRatio.WIDESCREEN
    assert DEFAULT_ASPECT_RATIO.value == "16:9"


def test_the_server_default_matches_the_domain_default():
    """A deployment that sets nothing must get the documented default."""
    from app.config import Settings

    assert Settings().teaser_aspect_ratio == DEFAULT_ASPECT_RATIO.value


@pytest.mark.parametrize(
    "ratio,expected",
    [
        (AspectRatio.WIDESCREEN, (1920, 1080)),
        (AspectRatio.VERTICAL, (1080, 1920)),
        (AspectRatio.SQUARE, (1080, 1080)),
        (AspectRatio.CLASSIC, (1440, 1080)),
        (AspectRatio.PORTRAIT, (1080, 1350)),
    ],
)
def test_every_offered_ratio_resolves_to_even_dimensions(ratio, expected):
    """H.264 rejects odd dimensions, so an offered ratio that produced one
    would fail at encode time rather than at validation."""
    width, height = output_resolution(ratio.value)

    assert (width, height) == expected
    assert width % 2 == 0 and height % 2 == 0


@pytest.mark.parametrize("ratio", list(AspectRatio))
def test_every_offered_ratio_builds_a_filter(ratio):
    assert "crop=" in build_filter(ratio.value)


# ----------------------------------------------------------------------
# Through the API
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_an_unknown_ratio_is_rejected(client, uploaded_video):
    response = queue(client, uploaded_video["video_id"], aspect_ratio="21:9")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@requires_ffmpeg
def test_a_ratio_shaped_like_an_injection_is_rejected(client, uploaded_video):
    """The value reaches an FFmpeg filter expression, so the closed set is not
    only about product choices."""
    response = queue(
        client, uploaded_video["video_id"], aspect_ratio="16:9;rm -rf /"
    )

    assert response.status_code == 422


@requires_ffmpeg
def test_omitting_the_ratio_stores_null(client, uploaded_video):
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    with user_session(OWNER_ID) as db:
        assert db.get(Job, job_id).aspect_ratio is None


@requires_ffmpeg
def test_the_chosen_ratio_is_stored_and_reported(client, uploaded_video):
    job_id = queue(
        client, uploaded_video["video_id"], aspect_ratio="1:1"
    ).json()["job_id"]

    with user_session(OWNER_ID) as db:
        assert db.get(Job, job_id).aspect_ratio == "1:1"
    assert client.get(f"/api/jobs/{job_id}").json()["aspect_ratio"] == "1:1"


# ----------------------------------------------------------------------
# In the pixels
# ----------------------------------------------------------------------
@requires_ffmpeg
@pytest.mark.parametrize(
    "ratio,width,height",
    [("16:9", 1920, 1080), ("9:16", 1080, 1920), ("1:1", 1080, 1080)],
)
def test_the_clips_are_cut_to_the_requested_shape(
    client, uploaded_video, ratio, width, height
):
    video_id = uploaded_video["video_id"]
    job_id = queue(client, video_id, aspect_ratio=ratio).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))
    assert job.status == "completed", job.error_message

    teasers = client.get(f"/api/videos/{video_id}/teasers?job_id={job_id}").json()
    assert teasers["teasers"], "no clips were produced"
    for teaser in teasers["teasers"]:
        assert (teaser["width"], teaser["height"]) == (width, height)


@requires_ffmpeg
def test_a_run_without_a_ratio_falls_back_to_the_server_default(
    client, uploaded_video, settings
):
    video_id = uploaded_video["video_id"]
    job_id = queue(client, video_id).json()["job_id"]

    run(job_id, StubProvider(good_candidates()))

    expected = output_resolution(settings.teaser_aspect_ratio)
    teasers = client.get(f"/api/videos/{video_id}/teasers?job_id={job_id}").json()
    first = teasers["teasers"][0]
    assert (first["width"], first["height"]) == expected


@requires_ffmpeg
def test_two_runs_of_one_video_can_have_different_shapes(client, uploaded_video):
    """The point of making this per-run: one source, two output formats."""
    video_id = uploaded_video["video_id"]

    wide = queue(client, video_id, aspect_ratio="16:9").json()["job_id"]
    tall = queue(client, video_id, aspect_ratio="9:16").json()["job_id"]
    run(wide, StubProvider(good_candidates()))
    run(tall, StubProvider(good_candidates()))

    def shape(job_id):
        body = client.get(f"/api/videos/{video_id}/teasers?job_id={job_id}").json()
        first = body["teasers"][0]
        return first["width"], first["height"]

    assert shape(wide) == (1920, 1080)
    assert shape(tall) == (1080, 1920)
