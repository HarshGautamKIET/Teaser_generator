"""Verdicts on clips: the ground truth this product can collect and a batch
annotation exercise cannot.

Every retrieval metric in `app/evaluation` needs labelled data, and the usual
way to get it is to sit a team down with someone else's webinar and mark the
spans that should have been chosen. That produces annotations, but not good
ones: the annotator does not know the material, has no stake in the result, and
is guessing at what a teaser of this video is for.

This project already has a better annotator in front of the clips. The person
who uploaded the source is judging their own content at the moment they are
deciding whether to post it, and the answer they are already forming -- would I
use this? -- is exactly the label the metrics need. Collecting it costs one
control on a card.

Written through the caller's own RLS-scoped session, so a clip belonging to
someone else is not "forbidden" here: it is not found, and nothing leaks about
whether the id is real.
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Teaser, TeaserFeedback, new_id

logger = logging.getLogger(__name__)


def set_verdict(
    db: Session, teaser_id: str, user_id: str, verdict: str, note: str | None = None
) -> TeaserFeedback:
    """Record or change this caller's verdict on one clip.

    Upsert rather than insert. A verdict is an opinion, and someone who watches
    a clip again and changes their mind is producing a better label than the
    first one, not a second label -- appending both would let one person weight
    their own clip twice in every metric computed over the corpus.

    The unique index in migrations/0012 enforces the same rule at the database,
    for a write that does not come through here.
    """
    teaser = db.get(Teaser, teaser_id)
    if teaser is None:
        raise NotFoundError("TEASER_NOT_FOUND", f"No teaser found with id {teaser_id}.")

    feedback = (
        db.query(TeaserFeedback)
        .filter(
            TeaserFeedback.teaser_id == teaser_id,
            TeaserFeedback.user_id == user_id,
        )
        .one_or_none()
    )

    if feedback is None:
        feedback = TeaserFeedback(
            id=new_id(),
            user_id=user_id,
            teaser_id=teaser_id,
            verdict=verdict,
            note=note,
        )
        db.add(feedback)
    else:
        feedback.verdict = verdict
        # Cleared when the new verdict arrives without one, so an old note
        # cannot end up attached to the opposite judgement.
        feedback.note = note

    db.commit()
    db.refresh(feedback)
    logger.info("Teaser %s marked %s", teaser_id, verdict)
    return feedback


def clear_verdict(db: Session, teaser_id: str, user_id: str) -> None:
    """Withdraw a verdict. Silent when there was none to withdraw.

    Idempotent on purpose: this backs a toggle, and clicking `keep` twice means
    "I did not mean that" rather than "this clip does not exist".
    """
    deleted = (
        db.query(TeaserFeedback)
        .filter(
            TeaserFeedback.teaser_id == teaser_id,
            TeaserFeedback.user_id == user_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    if deleted:
        logger.info("Verdict on teaser %s withdrawn", teaser_id)


def verdicts_for(db: Session, teaser_ids: list[str]) -> dict[str, str]:
    """Map teaser id -> verdict, for the clips the caller has judged.

    One query for a page of clips rather than one per card. Clips with no
    verdict are simply absent from the map, which is what `dict.get` already
    means -- an explicit None per unjudged clip would be a larger payload
    carrying the same information.
    """
    if not teaser_ids:
        return {}

    rows = (
        db.query(TeaserFeedback.teaser_id, TeaserFeedback.verdict)
        .filter(TeaserFeedback.teaser_id.in_(teaser_ids))
        .all()
    )
    return dict(rows)


def summarise(db: Session, video_id: str | None = None) -> tuple[dict[str, int], int]:
    """(verdict counts, total clips) for the caller, optionally for one video.

    The total is counted separately rather than derived from the verdicts,
    because the number that says whether the corpus is worth scoring is the one
    the verdicts cannot supply: how many clips still have no label.
    """
    teasers = db.query(Teaser.id)
    if video_id is not None:
        teasers = teasers.filter(Teaser.video_id == video_id)
    total = teasers.count()

    counts = db.query(TeaserFeedback.verdict, func.count(TeaserFeedback.id))
    if video_id is not None:
        counts = counts.join(Teaser, Teaser.id == TeaserFeedback.teaser_id).filter(
            Teaser.video_id == video_id
        )

    return dict(counts.group_by(TeaserFeedback.verdict).all()), total


