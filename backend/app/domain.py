"""Audience, style, and output format vocabulary (FR-004, FR-005)."""

from dataclasses import dataclass
from enum import Enum


class Audience(str, Enum):  # StrEnum needs 3.11; project targets 3.10
    GENERAL = "general"
    DEVELOPERS = "developers"
    BUSINESS_LEADERS = "business_leaders"
    STUDENTS = "students"


class Style(str, Enum):
    INFORMATIVE = "informative"
    PROMOTIONAL = "promotional"
    EMOTIONAL = "emotional"


class AspectRatio(str, Enum):
    """Output shapes a run may ask for.

    A closed set rather than a free string. The FFmpeg layer can crop to any
    ratio, but this value arrives from a client and ends up shaping a filter
    expression, so the API accepts only shapes the product actually offers --
    an enum makes an unknown one a 422 instead of something to sanitise.
    """

    WIDESCREEN = "16:9"    # YouTube, web embeds, presentations
    VERTICAL = "9:16"      # Shorts, Reels, TikTok
    SQUARE = "1:1"         # feed posts
    CLASSIC = "4:3"        # archival and slide-heavy source material
    PORTRAIT = "4:5"       # Instagram portrait


# Widescreen: most source material is already 16:9, so the default neither
# crops away picture nor assumes the output is destined for a phone.
DEFAULT_ASPECT_RATIO = AspectRatio.WIDESCREEN


# Guidance sent to Gemini, taken from AI_DESIGN.md.
AUDIENCE_GUIDANCE: dict[Audience, str] = {
    Audience.GENERAL: (
        "A broad general audience. Prefer moments that are broadly understandable "
        "without specialist knowledge."
    ),
    Audience.DEVELOPERS: (
        "Software developers and engineers. Prefer technical insights, "
        "implementation demonstrations, engineering lessons, and surprising "
        "technical results."
    ),
    Audience.BUSINESS_LEADERS: (
        "Business and technology leaders. Prefer business impact, ROI, measurable "
        "outcomes, market implications, and strategic insights."
    ),
    Audience.STUDENTS: (
        "Students and learners. Prefer educational explanations, clear learning "
        "value, and memorable insights."
    ),
}

STYLE_GUIDANCE: dict[Style, str] = {
    Style.INFORMATIVE: (
        "Informative: lead with facts, explanations, and clarity."
    ),
    Style.PROMOTIONAL: (
        "Promotional: lead with curiosity, strong hooks, benefits, and memorable "
        "outcomes."
    ),
    Style.EMOTIONAL: (
        "Emotional: lead with storytelling, reactions, surprise, conflict, and "
        "emotional engagement."
    ),
}


# ----------------------------------------------------------------------
# Source material
# ----------------------------------------------------------------------
class RecordingType(str, Enum):
    """What kind of long-form recording is being cut down.

    The pipeline was tuned for one shape of source -- a person talking through
    distinct topics -- and the tuning is wrong for the other two in ways that
    lose clips rather than merely producing weaker ones. A demo's payoff shot
    depends on the steps that set it up, and a training session is cumulative
    by design, so both score low on self-containment and get discarded before
    they are ever ranked.
    """

    WEBINAR = "webinar"
    DEMO = "demo"
    TRAINING = "training"


# The shape the settings were tuned for, so an unspecified run behaves exactly
# as it did before recording types existed.
DEFAULT_RECORDING_TYPE = RecordingType.WEBINAR


class CropMode(str, Enum):
    """How a frame is fitted to an output shape that is not its own.

    Derived from the recording type rather than chosen per run: centre-cropping
    screen content is not a preference, it is a defect. Nothing is stored for
    it -- the recording type is stored, and this follows from it.
    """

    CROP = "crop"  # fill the frame, discarding what falls outside it
    FIT = "fit"    # keep the whole frame, padding what is left over


@dataclass(frozen=True)
class RecordingProfile:
    """Pipeline settings that depend on what kind of recording this is.

    Every numeric field is optional and None means "use the server setting" --
    the same convention the per-run job columns already use. The webinar
    profile therefore overrides nothing: those settings are tuned for it, and
    introducing recording types must not silently retune the default path.
    """

    guidance: str
    # Replaces the strictest line of the standalone rule in the prompt. The
    # rest of that rule (start on a whole thought, do not open on a dangling
    # pronoun) holds for every source; only how much prior context a moment may
    # assume actually varies.
    context_rule: str
    crop_mode: CropMode = CropMode.CROP
    min_self_contained: float | None = None
    min_gap_seconds: int | None = None
    preferred_min_seconds: int | None = None
    preferred_max_seconds: int | None = None


RECORDING_PROFILES: dict[RecordingType, RecordingProfile] = {
    RecordingType.WEBINAR: RecordingProfile(
        guidance=(
            "A talk, panel, or webinar: someone presenting distinct topics to an "
            "audience. Prefer the moments where a claim is made and supported."
        ),
        context_rule=(
            "It must not depend on anything said earlier or later in the video."
        ),
        # Deliberately no overrides. See RecordingProfile.
    ),
    RecordingType.DEMO: RecordingProfile(
        guidance=(
            "A product demo or screen recording. Prefer the moment a result "
            "appears on screen -- the output, the finished state, the number that "
            "changed -- together with just enough of the action before it that the "
            "result is legible. Never select cursor movement, menu hunting, typing, "
            "or waiting for something to load."
        ),
        context_rule=(
            "It may assume the product has already been introduced, but what "
            "happens on screen must make sense without the earlier steps that led "
            "to it."
        ),
        # Screen recordings are mostly small text. Centre-cropping 16:9 to 9:16
        # keeps under a third of the width and takes the UI with it.
        crop_mode=CropMode.FIT,
        # A demo beat is a sequence -- action, then result -- so the strict
        # webinar threshold discards the payoff along with the setup.
        min_self_contained=4.0,
        # Demos move between features quickly; the webinar gap would rule out
        # two genuinely different features shown a few seconds apart.
        min_gap_seconds=5,
        # A workflow needs room to reach its result. Both are clamped to the
        # run's own maximum, so these only apply when it is raised.
        preferred_min_seconds=25,
        preferred_max_seconds=75,
    ),
    RecordingType.TRAINING: RecordingProfile(
        guidance=(
            "A training session or course recording, taught in modules that build "
            "on each other. Select at most one moment per module so the set covers "
            "the arc of the session rather than crowding into one lesson. Prefer "
            "the moment a concept is explained or demonstrated, not the recap."
        ),
        context_rule=(
            "It may assume general familiarity with the subject, but not a "
            "specific earlier example, exercise, or slide from this session."
        ),
        # Slide-heavy and often screen-shared; same reasoning as the demo.
        crop_mode=CropMode.FIT,
        # Cumulative material never scores as highly as a self-contained talk,
        # but a lesson that opens mid-exercise is still no use.
        min_self_contained=4.5,
        # Wide, so the selected moments land in different modules. Shrunk
        # automatically when the session is too short to afford it
        # (ranking_service.affordable_gap).
        min_gap_seconds=45,
        preferred_max_seconds=45,
    ),
}
