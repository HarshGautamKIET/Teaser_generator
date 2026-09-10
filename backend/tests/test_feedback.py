"""Verdicts on clips.

The evaluation corpus is collected here, one click at a time, so the properties
that matter are the ones that decide whether the corpus is trustworthy: one
verdict per person per clip, nobody can label somebody else's clip, and a
withdrawn verdict actually disappears rather than lingering as data.
"""

import pytest

from tests.conftest import requires_ffmpeg
from tests.test_generation import StubProvider, good_candidates, run


@pytest.fixture
def teaser_id(client, uploaded_video):
    """One real clip, cut by a real run, owned by the default caller."""
    job_id = client.post(
        f"/api/videos/{uploaded_video['video_id']}/generate",
        json={"audience": "developers", "style": "promotional"},
    ).json()["job_id"]
    run(job_id, StubProvider(good_candidates()))

    teasers = client.get(
        f"/api/videos/{uploaded_video['video_id']}/teasers"
    ).json()["teasers"]
    assert teasers, "the fixture run produced no clips"
    return teasers[0]["id"]


# ----------------------------------------------------------------------
# The round trip
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_a_verdict_is_recorded_and_returned_on_the_clip(client, teaser_id, uploaded_video):
    response = client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})
    assert response.status_code == 200, response.text
    assert response.json()["verdict"] == "keep"

    listing = client.get(f"/api/videos/{uploaded_video['video_id']}/teasers").json()
    judged = next(t for t in listing["teasers"] if t["id"] == teaser_id)
    assert judged["feedback"] == "keep"


@requires_ffmpeg
def test_an_unjudged_clip_reports_no_verdict(client, uploaded_video, teaser_id):
    listing = client.get(f"/api/videos/{uploaded_video['video_id']}/teasers").json()

    assert all(t["feedback"] is None for t in listing["teasers"])


@requires_ffmpeg
def test_a_second_verdict_replaces_the_first(client, teaser_id):
    """One person, one clip, one opinion. Appending both would let a single
    annotator weight their own clip twice in every metric."""
    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})
    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "discard"})

    summary = client.get("/api/teasers/feedback/summary").json()
    assert summary["kept"] == 0
    assert summary["discarded"] == 1


@requires_ffmpeg
def test_changing_the_verdict_clears_the_old_note(client, teaser_id):
    """A note written about "discard" must not end up attached to "keep"."""
    client.put(
        f"/api/teasers/{teaser_id}/feedback",
        json={"verdict": "discard", "note": "opens mid-sentence"},
    )
    body = client.put(
        f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"}
    ).json()

    assert body["note"] is None


@requires_ffmpeg
def test_a_verdict_can_be_withdrawn(client, teaser_id):
    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})

    assert client.delete(f"/api/teasers/{teaser_id}/feedback").status_code == 204
    assert client.get("/api/teasers/feedback/summary").json()["kept"] == 0


@requires_ffmpeg
def test_withdrawing_a_verdict_that_was_never_given_succeeds(client, teaser_id):
    """This backs a toggle: clicking `keep` twice means "I did not mean that"."""
    assert client.delete(f"/api/teasers/{teaser_id}/feedback").status_code == 204


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_an_unknown_verdict_is_rejected(client, teaser_id):
    response = client.put(
        f"/api/teasers/{teaser_id}/feedback", json={"verdict": "maybe"}
    )

    assert response.status_code == 422


@requires_ffmpeg
def test_an_oversized_note_is_rejected(client, teaser_id):
    response = client.put(
        f"/api/teasers/{teaser_id}/feedback",
        json={"verdict": "keep", "note": "x" * 501},
    )

    assert response.status_code == 422


def test_a_verdict_on_a_missing_clip_is_not_found(client):
    response = client.put(
        "/api/teasers/00000000-0000-0000-0000-000000000000/feedback",
        json={"verdict": "keep"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEASER_NOT_FOUND"


def test_feedback_requires_a_signed_in_caller(anonymous_client):
    response = anonymous_client.put(
        "/api/teasers/whatever/feedback", json={"verdict": "keep"}
    )

    assert response.status_code == 401


# ----------------------------------------------------------------------
# Isolation
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_another_user_cannot_judge_a_clip_they_do_not_own(
    client, other_client, teaser_id
):
    """Not "forbidden" -- not found. The response must leak nothing about
    whether the id is real, exactly like the media route."""
    response = other_client.put(
        f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"}
    )

    assert response.status_code == 404


@requires_ffmpeg
def test_a_verdict_is_invisible_to_another_account(client, other_client, teaser_id):
    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})

    assert other_client.get("/api/teasers/feedback/summary").json()["kept"] == 0


# ----------------------------------------------------------------------
# The summary
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_the_summary_counts_what_is_still_unjudged(client, teaser_id, uploaded_video):
    """The number that says whether the corpus is worth scoring. A summary of
    only keeps and discards looks complete at three labels out of ninety."""
    before = client.get("/api/teasers/feedback/summary").json()
    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})
    after = client.get("/api/teasers/feedback/summary").json()

    assert after["pending"] == before["pending"] - 1
    assert after["kept"] == 1


@requires_ffmpeg
def test_the_summary_can_be_narrowed_to_one_video(client, teaser_id, uploaded_video):
    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})
    scoped = client.get(
        f"/api/teasers/feedback/summary?video_id={uploaded_video['video_id']}"
    ).json()

    assert scoped["kept"] == 1


# ----------------------------------------------------------------------
# The bridge into the evaluation harness
# ----------------------------------------------------------------------
@requires_ffmpeg
def test_kept_clips_become_annotated_spans(client, teaser_id, uploaded_video):
    """A clip the user kept is a span that should have been selected. That is a
    ground-truth annotation produced as a side effect of using the tool."""
    from app.database import user_session
    from app.evaluation.harness import ground_truth_from_feedback

    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "keep"})

    with user_session(client.user_id) as db:
        truth = ground_truth_from_feedback(db, uploaded_video["video_id"])

    assert truth is not None
    assert truth.origin == "feedback"
    assert len(truth.spans) == 1


@requires_ffmpeg
def test_discarded_clips_do_not_become_annotations(client, teaser_id, uploaded_video):
    """These metrics score what a run returned against what it should have
    returned. A "should not" is already counted -- as a prediction that matched
    nothing -- and adding it as an annotation would count it twice."""
    from app.database import user_session
    from app.evaluation.harness import ground_truth_from_feedback

    client.put(f"/api/teasers/{teaser_id}/feedback", json={"verdict": "discard"})

    with user_session(client.user_id) as db:
        assert ground_truth_from_feedback(db, uploaded_video["video_id"]) is None


@requires_ffmpeg
def test_a_video_nobody_has_judged_has_no_derived_truth(client, uploaded_video, teaser_id):
    """None rather than an empty annotation set: zero annotations would score
    every run at precision 0.0 and drag a corpus average down with a row that
    actually means "unlabelled"."""
    from app.database import user_session
    from app.evaluation.harness import ground_truth_from_feedback

    with user_session(client.user_id) as db:
        assert ground_truth_from_feedback(db, uploaded_video["video_id"]) is None
