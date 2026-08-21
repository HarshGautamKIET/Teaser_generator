import { useMemo, useState } from "react";

import { listTeasers } from "../api";
import { useAsync } from "../async";
import { formatDate } from "../format";
import { AUDIENCE_OPTIONS, type LibraryTeaser } from "../types";
import Icon from "../ui/Icon";
import AsyncBoundary from "./AsyncBoundary";
import TeaserCard from "./TeaserCard";

const ALL = "all";

/** Every clip ever produced, across runs.
 *
 *  The generate flow shows one run and then forgets it. This is the shelf: work
 *  from different sources and audiences side by side, which is why each card
 *  has to say which run it came out of.
 */
export default function LibraryScreen() {
  const state = useAsync(listTeasers, []);
  const [source, setSource] = useState<string>(ALL);
  const [audience, setAudience] = useState<string>(ALL);

  const teasers = state.data?.teasers;

  // Filter options come from the clips themselves, so a filter can never offer
  // a source that would produce an empty shelf.
  const sources = useMemo(() => {
    const seen = new Map<string, string>();
    for (const teaser of teasers ?? []) seen.set(teaser.video_id, teaser.filename);
    return [...seen.entries()];
  }, [teasers]);

  const audiences = useMemo(() => {
    const seen = new Set((teasers ?? []).map((teaser) => teaser.audience));
    return AUDIENCE_OPTIONS.filter((option) => seen.has(option.value));
  }, [teasers]);

  const visible = (teasers ?? []).filter(
    (teaser) =>
      (source === ALL || teaser.video_id === source) &&
      (audience === ALL || teaser.audience === audience),
  );

  return (
    <AsyncBoundary state={state}>
      {({ teasers: all }) =>
        all.length === 0 ? (
          <section className="card">
            <div className="card-header">
              <span className="icon-tile">
                <Icon name="layout-grid" size={15} strokeWidth={2.2} />
              </span>
              <h2>Library</h2>
            </div>
            <p className="empty-note">
              No clips yet. Finish a generation run and every teaser it produces
              is kept here.
            </p>
          </section>
        ) : (
          <section className="card">
            <div className="card-header">
              <span className="icon-tile">
                <Icon name="layout-grid" size={15} strokeWidth={2.2} />
              </span>
              <h2>Library</h2>
              <div className="card-header-actions">
                <span className="badge o-num">
                  {visible.length === all.length
                    ? all.length
                    : `${visible.length} / ${all.length}`}
                </span>
              </div>
            </div>

            <div className="filter-bar">
              <label className="filter">
                <span className="filter-label">Source</span>
                <select
                  className="select"
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                >
                  <option value={ALL}>All videos</option>
                  {sources.map(([id, filename]) => (
                    <option key={id} value={id}>
                      {filename}
                    </option>
                  ))}
                </select>
              </label>

              <label className="filter">
                <span className="filter-label">Audience</span>
                <select
                  className="select"
                  value={audience}
                  onChange={(event) => setAudience(event.target.value)}
                >
                  <option value={ALL}>All audiences</option>
                  {audiences.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              {(source !== ALL || audience !== ALL) && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => {
                    setSource(ALL);
                    setAudience(ALL);
                  }}
                >
                  <Icon name="x" size={13} />
                  Clear
                </button>
              )}
            </div>

            {visible.length === 0 ? (
              <p className="empty-note">No clips match those filters.</p>
            ) : (
              <div className="teaser-grid">
                {visible.map((teaser) => (
                  <TeaserCard
                    key={teaser.id}
                    teaser={teaser}
                    context={<ClipOrigin teaser={teaser} />}
                  />
                ))}
              </div>
            )}
          </section>
        )
      }
    </AsyncBoundary>
  );
}

function ClipOrigin({ teaser }: { teaser: LibraryTeaser }) {
  return (
    <>
      <span className="teaser-context-source" title={teaser.filename}>
        <Icon name="film" size={12} />
        {teaser.filename}
      </span>
      <span className="badge badge-brand">
        {teaser.audience.replace("_", " ")} · {teaser.style}
      </span>
      <span className="teaser-context-date o-num">{formatDate(teaser.created_at)}</span>
    </>
  );
}
