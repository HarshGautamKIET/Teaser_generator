"""Audience, style, and output format vocabulary (FR-004, FR-005)."""

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
