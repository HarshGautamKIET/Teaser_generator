import { useEffect, useState, type ReactNode } from "react";

import { fetchTeaserMedia } from "../api";
import { timestamp } from "../format";
import type { Teaser } from "../types";
import Icon from "../ui/Icon";

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

/** Teaser media sits behind an ownership check, so the MP4 is fetched with the
 *  access token and played from a blob URL. The URL is revoked on unmount --
 *  without that, every re-render of a teaser list leaks a copy of the video. */
function useTeaserMedia(path: string): { url: string | null; failed: boolean } {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    fetchTeaserMedia(path)
      .then((created) => {
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        objectUrl = created;
        setUrl(created);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return { url, failed };
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
  const { url, failed } = useTeaserMedia(teaser.video_url);
  const length = teaser.duration_seconds ?? teaser.end_seconds - teaser.start_seconds;

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
