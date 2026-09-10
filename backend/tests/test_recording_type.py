"""What kind of recording the source is.

The pipeline's tuning constants were chosen for a talk: one person moving
through distinct topics. Demos and training sessions are not that shape, and the
mismatch does not merely produce weaker teasers -- a demo's payoff depends on the
steps that set it up, so it scores low on self-containment and is discarded
during validation. The run returns nothing at all.

So the tests that matter here are the ones that show the profile reaching the
two places it has to reach: the prompt the model is given, and the floor the
backend enforces afterwards. A profile applied in one but not the other is worse
than no profile, because it asks for moments it is about to throw away.

The webinar path is pinned separately: introducing recording types must not
retune the default, or every existing run silently changes behaviour.
"""

import pytest

from app.ai.base import AnalysisRequest, RawCandidate, RawCandidateList
from app.ai.prompt import build_prompt
from app.config import Settings, get_settings
from app.database import user_session
from app.domain import (
    DEFAULT_RECORDING_TYPE,
    RECORDING_PROFILES,
    Audience,
    CropMode,
    RecordingType,
    Style,
)
from app.media import CROP, FIT, build_filter
from app.models import Job
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, run, scores


def queue(client, video_id, **body):
    payload = {"audience": "developers", "style": "promotional", **body}
    return client.post(f"/api/videos/{video_id}/generate", json=payload)


def request_for(recording_type, **overrides):
    from pathlib import Path

    fields = dict(
        video_path=Path("source.mp4"),
        audience=Audience.DEVELOPERS,
        style=Style.INFORMATIVE,
        candidate_count=8,
        min_duration_seconds=20,
        max_duration_seconds=60,
        preferred_min_seconds=30,
        preferred_max_seconds=60,
        video_duration_seconds=1800.0,
        recording_type=recording_type,
    )
    return AnalysisRequest(**{**fields, **overrides})


def dependent_moment(start, end, self_contained):
    """A moment that needs its surroundings, scored strongly otherwise.

    This is the shape a demo produces: the result on screen is the payoff, and
    it does not stand alone as completely as a claim in a talk does.
    """
    return RawCandidate(
        start_seconds=start,
        end_seconds=end,
        title="The result appears",
        hook="Watch the number change.",
        reason="Shows the outcome.",
        scores=scores(9.0, self_contained=self_contained),
    )


# ----------------------------------------------------------------------
# The vocabulary
# ----------------------------------------------------------------------
def test_webinar_is_the_default():
    assert DEFAULT_RECORDING_TYPE is RecordingType.WEBINAR


def test_every_recording_type_has_a_profile():
    """A type without a profile is a KeyError inside a background worker,
    where nobody is waiting to see it."""
    assert set(RECORDING_PROFILES) == set(RecordingType)


def test_the_default_profile_overrides_nothing():
    """The settings are tuned for a talk, so the webinar profile must defer to
    them. If it ever carries a value of its own, every deployment that tuned
    .env is silently overruled and every pre-existing run changes behaviour."""
    profile = RECORDING_PROFILES[DEFAULT_RECORDING_TYPE]

    assert profile.min_self_contained is None
    assert profile.min_gap_seconds is None
    assert profile.preferred_min_seconds is None
    assert profile.preferred_max_seconds is None
    assert profile.crop_mode is CropMode.CROP


def test_crop_modes_match_the_media_layer():
    """domain.CropMode is what the API validates; the ffmpeg module carries
    plain strings. They are separate on purpose (the media layer imports no
    policy), which makes them able to drift."""
    assert {mode.value for mode in CropMode} == {CROP, FIT}


# ----------------------------------------------------------------------
# The prompt
# ----------------------------------------------------------------------
@pytest.mark.parametrize("recording_type", list(RecordingType))
def test_each_type_states_its_source_material(recording_type):
    prompt = build_prompt(request_for(recording_type))

    assert "SOURCE MATERIAL" in prompt
    assert RECORDING_PROFILES[recording_type].guidance in prompt


@pytest.mark.parametrize("recording_type", list(RecordingType))
def test_each_type_states_its_own_context_rule(recording_type):
    """The standalone rule is the reason demos returned nothing. Lowering the
    numeric floor without relaxing the prompt would leave the model refusing to
    propose the moments the floor now permits."""
    prompt = build_prompt(request_for(recording_type))

    assert RECORDING_PROFILES[recording_type].context_rule in prompt


def test_a_demo_is_not_told_to_reject_all_prior_context():
    webinar_rule = RECORDING_PROFILES[RecordingType.WEBINAR].context_rule
    prompt = build_prompt(request_for(RecordingType.DEMO))

    assert webinar_rule not in prompt


def test_the_default_prompt_is_unchanged_by_the_new_field():
    """An AnalysisRequest built without a recording type -- as every caller
    before this feature did -- must produce the webinar prompt."""
    explicit = build_prompt(request_for(RecordingType.WEBINAR))
    from pathlib import Path

    implicit = build_prompt(
        AnalysisRequest(
            video_path=Path("source.mp4"),
            audience=Audience.DEVELOPERS,
            style=Style.INFORMATIVE,
            candidate_count=8,
            min_duration_seconds=20,
            max_duration_seconds=60,
            preferred_min_seconds=30,
            preferred_max_seconds=60,
            video_duration_seconds=1800.0,
        )
    )

    assert implicit == explicit


# ----------------------------------------------------------------------
# The output shape
# ----------------------------------------------------------------------
def test_fit_keeps_the_whole_frame():
    """Centre-cropping 16:9 to 9:16 keeps under a third of the width, and a
    demo's value is the UI text that is usually the first thing outside it."""
    built = build_filter("9:16", FIT)

    assert "force_original_aspect_ratio=decrease" in built
    assert "pad=1080:1920" in built
    assert "crop=" not in built


def test_crop_remains_the_default_mode():
    assert build_filter("9:16") == build_filter("9:16", CROP)
    assert "crop=" in build_filter("9:16")


def test_an_unknown_crop_mode_is_refused():
    from app.media import MediaError

    with pytest.raises(MediaError, match="Unknown crop mode"):
        build_filter("9:16", "letterbox")


@pytest.mark.parametrize("recording_type", [RecordingType.DEMO, RecordingType.TRAINING])
def test_screen_heavy_types_fit_rather_than_crop(recording_type):
    assert RECORDING_PROFILES[recording_type].crop_mode is CropMode.FIT


# ----------------------------------------------------------------------
# Through the API
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_an_unknown_recording_type_is_rejected(client, uploaded_video):
    response = queue(client, uploaded_video["video_id"], recording_type="podcast")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@requires_ffmpeg
def test_the_chosen_type_is_recorded_on_the_run(client, uploaded_video):
    response = queue(client, uploaded_video["video_id"], recording_type="demo")

    assert response.status_code == 202
    with user_session(OWNER_ID) as db:
        assert db.get(Job, response.json()["job_id"]).recording_type == "demo"


@requires_ffmpeg
def test_omitting_the_type_stores_null_rather_than_a_copied_default(
    client, uploaded_video
):
    """A concrete default written in here would freeze today's value into every
    future row, exactly as migrations/0005 avoided for aspect ratio."""
    response = queue(client, uploaded_video["video_id"])

    with user_session(OWNER_ID) as db:
        assert db.get(Job, response.json()["job_id"]).recording_type is None


@requires_ffmpeg
def test_the_type_is_reported_back(client, uploaded_video):
    job_id = queue(
        client, uploaded_video["video_id"], recording_type="training"
    ).json()["job_id"]

    body = client.get(f"/api/jobs/{job_id}").json()

    assert body["recording_type"] == "training"


# ----------------------------------------------------------------------
# The profile reaching the pipeline
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_the_profile_reaches_the_prompt(client, uploaded_video):
    """The stub captures what the provider was actually asked, which is the
    only way to tell a profile that is applied from one that is merely stored."""
    job_id = queue(
        client, uploaded_video["video_id"], recording_type="demo"
    ).json()["job_id"]

    captured = {}

    class CapturingProvider(StubProvider):
        def analyze_video(self, request):
            captured["request"] = request
            return RawCandidateList(candidates=self._candidates or [])

    provider = CapturingProvider([dependent_moment(0.0, 2.5, self_contained=5.0)])
    run(job_id, provider)

    request = captured["request"]
    assert request.recording_type is RecordingType.DEMO
    assert request.min_self_contained == 4.0
    # Not the profile's 5s exactly: the fixture video is eight seconds long and
    # affordable_gap divides what is left after the clips themselves between the
    # gaps. What matters is that the demo's preference is what got shrunk --
    # asking for the webinar's 15s here would leave the same reduced number and
    # hide the profile never being consulted.
    demo_gap = RECORDING_PROFILES[RecordingType.DEMO].min_gap_seconds
    assert 0 < request.min_gap_seconds <= demo_gap


@requires_ffmpeg
def test_a_demo_moment_survives_the_floor_that_would_drop_it_as_a_webinar(
    client, uploaded_video
):
    """The whole point of the feature, stated as one comparison.

    The same moment, scored the same way, run twice: discarded under the talk's
    threshold and kept under the demo's. Without this the pipeline serves one of
    the three kinds of source it is meant to serve.
    """
    settings = get_settings()
    below_webinar_floor = settings.teaser_min_self_contained - 2.0
    assert below_webinar_floor > RECORDING_PROFILES[RecordingType.DEMO].min_self_contained

    video_id = uploaded_video["video_id"]
    moments = [dependent_moment(0.0, 2.5, self_contained=below_webinar_floor)]

    as_webinar = run(queue(client, video_id).json()["job_id"], StubProvider(moments))
    as_demo = run(
        queue(client, video_id, recording_type="demo").json()["job_id"],
        StubProvider(moments),
    )

    assert as_webinar.status == "failed"
    assert as_webinar.error_code == "NO_SELF_CONTAINED_MOMENTS"
    assert as_demo.status == "completed"


@requires_ffmpeg
def test_a_training_run_spaces_its_clips_more_widely_than_a_talk(
    client, uploaded_video
):
    """Training material is taught in modules, so three clips from one lesson
    are worse than three from three. The gap is the mechanism, and it is only
    honest if it is larger than the talk's."""
    training = RECORDING_PROFILES[RecordingType.TRAINING].min_gap_seconds

    assert training > get_settings().teaser_min_gap_seconds


def test_a_profile_may_set_zero_without_falling_through_to_the_setting():
    """`_or_default` exists because `override or default` would read a
    deliberate 0 as absent and quietly substitute the server's value."""
    from app.services.generation_service import _or_default

    assert _or_default(0, 15) == 0
    assert _or_default(0.0, 7.0) == 0.0
    assert _or_default(None, 15) == 15


def test_the_settings_still_own_the_default_path():
    """Every value the webinar profile declines to override must come from
    Settings, so tuning .env keeps working."""
    from app.services.generation_service import _or_default

    settings = Settings()
    profile = RECORDING_PROFILES[RecordingType.WEBINAR]

    assert _or_default(
        profile.min_self_contained, settings.teaser_min_self_contained
    ) == settings.teaser_min_self_contained
    assert _or_default(
        profile.min_gap_seconds, settings.teaser_min_gap_seconds
    ) == settings.teaser_min_gap_seconds
