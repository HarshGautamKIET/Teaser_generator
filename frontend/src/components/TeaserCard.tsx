import { useState, type ReactNode } from "react";

import { clearFeedback, setFeedback } from "../api";
import { timestamp } from "../format";
import type { Teaser, Verdict } from "../types";
import Icon from "../ui/Icon";
import { useAuthedMedia } from "../useMedia";

const SCORE_LABELS: Record<string, string> = {
  hook: "Hook",
  audience_relevance: "Audience fit",
  information_value: "Information",
  engagement: "Engagement",
  self_contained: "Self-contained",
};

interface Props {
  teaser: Teaser;
  /** Where this clip came from. Omitted inside a single run, where every card
   *  shares one source and saying so on each would be noise; supplied in the
   *  library, where `#1` means nothing without the run that ranked it. */
  context?: ReactNode;
}

/** `teaser-2-the-opening-claim.mp4`. Punctuation and spaces are folded away so
 *  the name survives every filesystem it might land on. */
function downloadName(teaser: Teaser): string {
  const slug = teaser.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `teaser-${teaser.rank}${slug ? `-${slug}` : ""}.mp4`;
}

export default function TeaserCard({ teaser, context }: Props) {
  const { url, failed } = useAuthedMedia(teaser.video_url);
  const length = teaser.duration_seconds ?? teaser.end_seconds - teaser.start_seconds;

  // Held locally rather than lifted, because the answer is per-card and nothing
  // above needs it to re-render. The initial value comes from the clip itself
  // so the control is already in its correct state on first paint.
  const [verdict, setVerdict] = useState<Verdict | null>(teaser.feedback);
  const [saving, setSaving] = useState(false);

  /** Clicking the active verdict withdraws it. Someone who mis-clicked should
   *  be able to undo without a third control, and a withdrawn verdict is more
   *  honest ground truth than one they did not mean. */
  async function judge(next: Verdict) {
    if (saving) return;
    const previous = verdict;
    const target = previous === next ? null : next;

    // Optimistic: the button responds immediately and reverts if the write
    // fails. A verdict is a one-click judgement and a spinner between the click
    // and the state change is enough friction to stop people giving them.
    setVerdict(target);
    setSaving(true);
    try {
      if (target === null) {
        await clearFeedback(teaser.id);
      } else {
        await setFeedback(teaser.id, target);
      }
    } catch {
      setVerdict(previous);
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="teaser">
      <div className="teaser-video">
        {url ? (
          <video src={url} controls preload="metadata" playsInline />
        ) : (
          <div className="teaser-video-placeholder">
            {failed ? "Video unavailable" : "Loading video…"}
          </div>
        )}
        <span className="badge badge-brand teaser-rank o-num">#{teaser.rank}</span>
      </div>

      <div className="teaser-head">
        <h3 className="teaser-title">{teaser.title}</h3>
        <span className="teaser-score o-num" title="Weighted score across all five dimensions">
          {teaser.score.toFixed(1)}
        </span>
      </div>

      {context && <div className="teaser-context">{context}</div>}

      <p className="teaser-hook">“{teaser.hook}”</p>

      <p className="teaser-meta o-num">
        {timestamp(teaser.start_seconds)} – {timestamp(teaser.end_seconds)}
        <span className="teaser-meta-sep">·</span>
        {Math.round(length)}s
        {teaser.width && teaser.height && (
          <>
            <span className="teaser-meta-sep">·</span>
            {teaser.width}×{teaser.height}
          </>
        )}
      </p>

      <div className="teaser-reason">
        <span className="teaser-reason-label">Why this moment</span>
        <p>{teaser.reason}</p>
      </div>

      {Object.keys(teaser.scores).length > 0 && (
        <ul className="scores">
          {Object.entries(teaser.scores).map(([key, value]) => (
            <li key={key}>
              <span>{SCORE_LABELS[key] ?? key}</span>
              <span className="track">
                <span
                  className="track-fill"
                  style={{ width: `${Math.min(100, (value / 10) * 100)}%` }}
                />
              </span>
              <span className="score-number o-num">{value.toFixed(1)}</span>
            </li>
          ))}
        </ul>
      )}

      {/* The evaluation corpus, collected one click at a time. Asked here
          rather than in a separate review screen because this is the moment the
          user is already deciding whether to post the clip — the judgement
          exists either way, and this is the only place it is free to capture. */}
      <div className="teaser-verdict" role="group" aria-label="Would you post this clip?">
        <span className="teaser-verdict-label">Would you post this?</span>
        <button
          type="button"
          className={`btn btn-sm${verdict === "keep" ? " btn-brand" : " btn-secondary"}`}
          aria-pressed={verdict === "keep"}
          disabled={saving}
          onClick={() => judge("keep")}
        >
          <Icon name="check" size={13} />
          Keep
        </button>
        <button
          type="button"
          className={`btn btn-sm${verdict === "discard" ? " btn-brand" : " btn-secondary"}`}
          aria-pressed={verdict === "discard"}
          disabled={saving}
          onClick={() => judge("discard")}
        >
          <Icon name="x" size={13} />
          No
        </button>
      </div>

      {/* Named from what the clip is, not from its record id: a filename is
          something the user keeps, and an internal identifier means nothing to
          them once it is sitting in a downloads folder. */}
      <a
        className="btn btn-secondary btn-sm btn-full"
        href={url ?? undefined}
        aria-disabled={url === null}
        download={downloadName(teaser)}
      >
        <Icon name="download" size={13} />
        Download MP4
      </a>
    </article>
  );
}
