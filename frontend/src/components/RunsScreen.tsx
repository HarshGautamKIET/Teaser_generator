import { useEffect, useMemo, useState } from "react";

import { listJobs } from "../api";
import { useAsync } from "../async";
import { formatDateTime } from "../format";
import {
  AUDIENCE_OPTIONS,
  STATUS_LABELS,
  type JobStatus,
  type JobSummary,
} from "../types";
import Icon from "../ui/Icon";
import AsyncBoundary from "./AsyncBoundary";

const ALL = "all";
const PAGE_SIZE = 15;
/** While something is running, the list refreshes on its own. Slow enough not
 *  to hammer the API, fast enough that a finished run does not sit stale. */
const LIVE_REFRESH_MS = 4000;

interface Props {
  videoId: string | null;
  onClearFilter: () => void;
  onOpenRun: (job: JobSummary) => void;
  onRetry: (job: JobSummary) => Promise<void>;
}

const TERMINAL: JobStatus[] = ["completed", "failed", "cancelled"];

function isRunning(job: JobSummary): boolean {
  return !TERMINAL.includes(job.status);
}

/** Status as a row badge. A run still in flight shows the stage it reached
 *  rather than a generic "Running", so a stuck job is visibly stuck. */
function RunStatus({ job }: { job: JobSummary }) {
  if (job.status === "failed") {
    return (
      <span className="status status-failed" title={job.error_message ?? undefined}>
        <span className="status-dot" />
        Failed
      </span>
    );
  }
  if (job.status === "completed") {
    return (
      <span className="status">
        <span className="status-dot" />
        Success
      </span>
    );
  }
  // Neutral, not red: the run was stopped on purpose and did not go wrong.
  if (job.status === "cancelled") {
    return (
      <span className="status">
        <span className="status-dot" />
        Cancelled
      </span>
    );
  }
  return (
    <span className="status status-pending">
      <span className="status-dot status-dot-pulse" />
      {STATUS_LABELS[job.status]}
    </span>
  );
}

export default function RunsScreen({
  videoId,
  onClearFilter,
  onOpenRun,
  onRetry,
}: Props) {
  const state = useAsync(() => listJobs(videoId ?? undefined), [videoId]);

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>(ALL);
  const [audience, setAudience] = useState<string>(ALL);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [retrying, setRetrying] = useState<string | null>(null);

  const jobs = useMemo(() => state.data?.jobs ?? [], [state.data]);
  const live = jobs.some(isRunning);
  const { reload } = state;

  // Only polls while something is actually in flight; a settled history is
  // static and re-fetching it every few seconds would be pure noise.
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(reload, LIVE_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [live, reload]);

  const visible = jobs.filter((job) => {
    const needle = query.trim().toLowerCase();
    return (
      (status === ALL || job.status === status) &&
      (audience === ALL || job.audience === audience) &&
      (needle === "" || job.filename.toLowerCase().includes(needle))
    );
  });

  const filtered = query.trim() !== "" || status !== ALL || audience !== ALL;
  const shown = visible.slice(0, limit);

  const handleRetry = async (job: JobSummary) => {
    setRetrying(job.job_id);
    try {
      await onRetry(job);
      reload();
    } catch {
      /* The failure is already surfaced by the page-level alert. */
    } finally {
      setRetrying(null);
    }
  };

  return (
    <AsyncBoundary state={state}>
      {() => (
        <section className="card">
          <div className="card-header">
            <span className="icon-tile">
              <Icon name="history" size={15} strokeWidth={2.2} />
            </span>
            <h2>Runs</h2>
            <div className="card-header-actions">
              {live && (
                <span className="live-pill" title="A run is in progress">
                  <span className="status-dot status-dot-pulse" />
                  Live
                </span>
              )}
              {videoId && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={onClearFilter}
                >
                  <Icon name="x" size={13} />
                  Show all videos
                </button>
              )}
              <span className="badge o-num">
                {filtered ? `${visible.length} / ${jobs.length}` : jobs.length}
              </span>
              <button
                type="button"
                className="icon-btn"
                aria-label="Refresh"
                title="Refresh"
                onClick={reload}
              >
                <Icon name="refresh-cw" size={15} />
              </button>
            </div>
          </div>

          {jobs.length === 0 ? (
            <p className="empty-note">
              {videoId
                ? "This video has not been processed yet."
                : "No runs yet. Generate teasers from a video and each attempt is recorded here."}
            </p>
          ) : (
            <>
              <div className="filter-bar">
                <label className="filter filter-grow">
                  <span className="filter-label">Search</span>
                  <div className="input-wrap">
                    <input
                      className="input input-sm"
                      type="search"
                      placeholder="Filter by source filename…"
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        setLimit(PAGE_SIZE);
                      }}
                    />
                  </div>
                </label>

                <label className="filter">
                  <span className="filter-label">Status</span>
                  <select
                    className="select"
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                  >
                    <option value={ALL}>Any status</option>
                    <option value="completed">Success</option>
                    <option value="failed">Failed</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="queued">Queued</option>
                  </select>
                </label>

                <label className="filter">
                  <span className="filter-label">Audience</span>
                  <select
                    className="select"
                    value={audience}
                    onChange={(event) => setAudience(event.target.value)}
                  >
                    <option value={ALL}>Any audience</option>
                    {AUDIENCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                {filtered && (
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => {
                      setQuery("");
                      setStatus(ALL);
                      setAudience(ALL);
                    }}
                  >
                    <Icon name="x" size={13} />
                    Clear
                  </button>
                )}
              </div>

              {visible.length === 0 ? (
                <p className="empty-note">No runs match those filters.</p>
              ) : (
                <>
                  <div className="table table-runs">
                    <div className="table-head">
                      <span>Source</span>
                      <span>Started</span>
                      <span>Audience</span>
                      <span>Clips</span>
                      <span>Status</span>
                      <span />
                    </div>

                    {shown.map((job) => (
                      <div className="table-row table-row-split" key={job.job_id}>
                        <button
                          type="button"
                          className="table-row-main"
                          onClick={() => onOpenRun(job)}
                        >
                          <span className="cell-activity">
                            <span className="icon-tile icon-tile-neutral icon-tile-sm">
                              <Icon name="film" size={12} strokeWidth={2.2} />
                            </span>
                            <span className="cell-name">{job.filename}</span>
                          </span>

                          <span className="cell-muted o-num">
                            {formatDateTime(job.created_at)}
                          </span>
                          <span className="cell-muted">
                            {job.audience.replace("_", " ")} · {job.style}
                          </span>
                          <span className="o-num">{job.teaser_count}</span>
                          <span>
                            <RunStatus job={job} />
                          </span>
                        </button>

                        <span className="cell-actions">
                          {job.status === "failed" ? (
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              title="Run this source and audience again"
                              disabled={retrying === job.job_id}
                              onClick={() => handleRetry(job)}
                            >
                              <Icon name="rotate-ccw" size={13} />
                              {retrying === job.job_id ? "Queueing" : "Retry"}
                            </button>
                          ) : (
                            <Icon name="chevron-right" size={15} />
                          )}
                        </span>
                      </div>
                    ))}
                  </div>

                  {visible.length > shown.length && (
                    <div className="card-footer-actions">
                      <span className="cell-muted">
                        Showing {shown.length} of {visible.length}
                      </span>
                      <button
                        type="button"
                        className="btn btn-outline btn-sm"
                        onClick={() => setLimit((current) => current + PAGE_SIZE)}
                      >
                        Load more
                      </button>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </section>
      )}
    </AsyncBoundary>
  );
}
