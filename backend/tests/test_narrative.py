"""What the run says about the video as a whole.

The clips were the only output, which left the product able to show which
moments it picked but not what the video was. Per-clip titles and hooks are not
a summary of the source -- they describe the excerpts.

The distinction these tests exist to hold is between the two kinds of AI output
the pipeline now handles. A candidate that fails validation costs the run a
clip, and if none survive the run fails. A summary that fails validation costs
the run a summary, and nothing else. Every rule the candidates get -- strings
normalised and capped, timestamps checked against the real duration, failures
discarded rather than repaired -- applies here too, with a different
consequence.
"""

import pytest

from app.ai.base import (
    MAX_CHAPTERS,
    MAX_KEYWORDS,
    MAX_SUMMARY_CHARS,
    RawCandidateList,
    RawChapter,
)
from app.ai.fake import FakeProvider
from app.ai.prompt import build_prompt
from app.database import user_session
from app.models import Job
from app.services.analysis_service import Narrative, validate_narrative
from tests.conftest import OWNER_ID, requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run
from tests.test_recording_type import queue, request_for

from app.domain import RecordingType


def analysis(**fields) -> RawCandidateList:
    """A response carrying narrative fields and no candidates.

    The candidates are irrelevant to everything below: validate_narrative reads
    the other three fields and is never given a reason to look at them.
    """
    return RawCandidateList(candidates=[], **fields)


def chapter(start, end, title="A section") -> RawChapter:
    return RawChapter(start_seconds=start, end_seconds=end, title=title)


# ----------------------------------------------------------------------
# Absence is not failure
# ----------------------------------------------------------------------
def test_a_response_with_no_narrative_validates_to_an_empty_one():
    """The whole reason these fields default rather than being required."""
    narrative = validate_narrative(analysis(), video_duration=600.0)

    assert narrative == Narrative()
    assert not narrative


def test_an_empty_narrative_is_falsy_and_a_populated_one_is_not():
    assert not Narrative()
    assert not Narrative(summary="", chapters=[], keywords=[])
    assert Narrative(summary="Something")
    assert Narrative(keywords=["one"])
    assert Narrative(chapters=[chapter(0, 1)])


def test_validation_never_raises_on_hostile_input():
    """Nothing here reaches a subprocess or a file, so the correct response to
    garbage is to drop it, not to fail a run that produced good clips."""
    narrative = validate_narrative(
        analysis(
            summary="\x00\x01\x02",
            keywords=["", "   ", "\x00"],
            chapters=[chapter(-1, -2, ""), chapter(500, 400)],
        ),
        video_duration=600.0,
    )

    assert narrative == Narrative()


# ----------------------------------------------------------------------
# The summary
# ----------------------------------------------------------------------
def test_the_summary_is_normalised_like_every_other_ai_string():
    narrative = validate_narrative(
        analysis(summary="  A talk\x00about   RAG.  "), video_duration=600.0
    )

    assert narrative.summary == "A talk about RAG."


def test_an_oversized_summary_is_truncated_rather_than_rejected():
    narrative = validate_narrative(
        analysis(summary="x" * (MAX_SUMMARY_CHARS * 2)), video_duration=600.0
    )

    assert len(narrative.summary) == MAX_SUMMARY_CHARS
    assert narrative.summary.endswith("…")


# ----------------------------------------------------------------------
# Keywords
# ----------------------------------------------------------------------
def test_keywords_are_deduplicated_case_insensitively():
    """"RAG" and "rag" are one keyword to a reader and two to a set."""
    narrative = validate_narrative(
        analysis(keywords=["RAG", "rag", "RAG ", "Vector Search"]),
        video_duration=600.0,
    )

    assert narrative.keywords == ["RAG", "Vector Search"]


def test_keywords_are_capped():
    narrative = validate_narrative(
        analysis(keywords=[f"topic {n}" for n in range(MAX_KEYWORDS * 3)]),
        video_duration=600.0,
    )

    assert len(narrative.keywords) == MAX_KEYWORDS


# ----------------------------------------------------------------------
# Chapters
# ----------------------------------------------------------------------
def test_chapters_are_returned_in_order_whatever_order_they_arrived_in():
    narrative = validate_narrative(
        analysis(chapters=[chapter(120, 180, "Third"), chapter(0, 60, "First"),
                           chapter(60, 120, "Second")]),
        video_duration=180.0,
    )

    assert [c.title for c in narrative.chapters] == ["First", "Second", "Third"]


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(lambda: chapter(-5, 10), id="negative start"),
        pytest.param(lambda: chapter(10, 5), id="ends before it starts"),
        pytest.param(lambda: chapter(10, 10), id="zero length"),
        pytest.param(lambda: chapter(700, 800), id="starts past the video"),
        pytest.param(lambda: chapter(0, 60, "  "), id="empty title"),
    ],
)
def test_a_chapter_that_does_not_hold_up_is_discarded(bad):
    narrative = validate_narrative(analysis(chapters=[bad()]), video_duration=600.0)

    assert narrative.chapters == []


def test_a_chapter_overrunning_the_end_is_clamped_not_dropped():
    """Unlike a clip window, the only thing downstream is a contents entry, so
    losing the last section of the video tells the reader less than trimming
    it does."""
    narrative = validate_narrative(
        analysis(chapters=[chapter(500, 9999, "The end")]), video_duration=600.0
    )

    assert len(narrative.chapters) == 1
    assert narrative.chapters[0].end_seconds == 600.0


def test_one_bad_chapter_does_not_take_the_good_ones_with_it():
    narrative = validate_narrative(
        analysis(chapters=[chapter(0, 60, "Good"), chapter(-1, -2, "Bad"),
                           chapter(60, 120, "Also good")]),
        video_duration=600.0,
    )

    assert [c.title for c in narrative.chapters] == ["Good", "Also good"]


def test_chapters_are_capped():
    narrative = validate_narrative(
        analysis(
            chapters=[chapter(n * 10, n * 10 + 10) for n in range(MAX_CHAPTERS * 2)]
        ),
        video_duration=10_000.0,
    )

    assert len(narrative.chapters) == MAX_CHAPTERS


# ----------------------------------------------------------------------
# The prompt asks for them
# ----------------------------------------------------------------------
def test_the_prompt_asks_for_all_three():
    prompt = build_prompt(request_for(RecordingType.WEBINAR))

    assert "ALSO DESCRIBE THE VIDEO AS A WHOLE" in prompt
    assert "summary:" in prompt
    assert "chapters:" in prompt
    assert "keywords:" in prompt


def test_the_prompt_bounds_chapters_by_the_real_duration():
    """Stated in the request as well as enforced afterwards, for the same
    reason the duration rules are: asking for what will be enforced is cheaper
    than discarding what comes back."""
    prompt = build_prompt(
        request_for(RecordingType.WEBINAR, video_duration_seconds=1234.5)
    )

    assert "1234.5 seconds" in prompt


# ----------------------------------------------------------------------
# The offline provider
# ----------------------------------------------------------------------
def test_the_fake_provider_labels_its_narrative():
    """Its output must never be mistakable for real analysis, and a plausible
    unmarked summary would be the easiest part of the demo to mistake."""
    raw = FakeProvider().analyze_video(request_for(RecordingType.WEBINAR))

    assert "[FAKE]" in raw.summary
    assert raw.chapters and all("[FAKE]" in c.title for c in raw.chapters)
    assert raw.keywords and all("[FAKE]" in k for k in raw.keywords)


def test_the_fake_providers_chapters_survive_validation():
    """A fixture that produced narrative the validator then dropped would make
    the offline rehearsal quietly show nothing."""
    request = request_for(RecordingType.WEBINAR, video_duration_seconds=600.0)

    narrative = validate_narrative(FakeProvider().analyze_video(request), 600.0)

    assert narrative.summary and narrative.chapters and narrative.keywords


# ----------------------------------------------------------------------
# Through the pipeline
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_a_completed_run_records_what_the_ai_said_about_the_video(
    client, uploaded_video
):
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    raw = RawCandidateList(
        candidates=good_candidates(),
        summary="A short talk about testing.",
        chapters=[chapter(0.0, 4.0, "Opening"), chapter(4.0, 7.9, "Closing")],
        keywords=["testing", "pytest"],
    )

    class NarratingProvider(StubProvider):
        def analyze_video(self, request):
            return raw

    job = run(job_id, NarratingProvider())

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        stored = db.get(Job, job_id)
        assert stored.summary == "A short talk about testing."
        assert [c["title"] for c in stored.chapters] == ["Opening", "Closing"]
        assert stored.keywords == ["testing", "pytest"]


@requires_ffmpeg
def test_a_run_without_narrative_still_produces_teasers(client, uploaded_video):
    """The guarantee the whole feature rests on: this is additional output, so
    a model that returns moments and no summary must not cost anyone a run."""
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    job = run(job_id, StubProvider(good_candidates()))

    assert job.status == "completed"
    with user_session(OWNER_ID) as db:
        stored = db.get(Job, job_id)
        assert stored.summary is None
        assert stored.chapters is None
        assert stored.keywords is None


@requires_ffmpeg
def test_the_narrative_is_reported_back(client, uploaded_video):
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]

    class NarratingProvider(StubProvider):
        def analyze_video(self, request):
            return RawCandidateList(
                candidates=good_candidates(),
                summary="A short talk about testing.",
                chapters=[chapter(0.0, 4.0, "Opening")],
                keywords=["testing"],
            )

    run(job_id, NarratingProvider())
    body = client.get(f"/api/jobs/{job_id}").json()

    assert body["summary"] == "A short talk about testing."
    assert body["chapters"] == [
        {"start_seconds": 0.0, "end_seconds": 4.0, "title": "Opening"}
    ]
    assert body["keywords"] == ["testing"]


@requires_ffmpeg
def test_absent_narrative_is_reported_as_empty_lists_not_null(
    client, uploaded_video
):
    """NULL and [] mean the same thing to a reader, so the API settles it once
    rather than making every client handle two kinds of absence."""
    job_id = queue(client, uploaded_video["video_id"]).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    body = client.get(f"/api/jobs/{job_id}").json()

    assert body["summary"] is None
    assert body["chapters"] == []
    assert body["keywords"] == []
