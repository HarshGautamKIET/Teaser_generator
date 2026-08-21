import { useMemo, useState } from "react";

import { listJobs, listTeasers } from "../api";
import { useAsync } from "../async";
import { formatDate, formatDuration } from "../format";
import type { JobSummary, LibraryTeaser } from "../types";
import Icon from "../ui/Icon";
import AsyncBoundary from "./AsyncBoundary";

const RANGES = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
] as const;

type RangeDays = (typeof RANGES)[number]["days"];

interface Props {
  onOpenRun: (job: JobSummary) => void;
}

interface Totals {
  jobs: JobSummary[];
  teasers: LibraryTeaser[];
}

function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

/** The cutoff for a range, so every figure on the page describes one window. */
function cutoffFor(days: RangeDays): number {
  const start = startOfDay(new Date());
  start.setDate(start.getDate() - (days - 1));
  return start.getTime();
}

/** Clips per bucket across the range, oldest first.
 *
 *  Ninety daily bars would be unreadable at this width, so longer ranges are
 *  grouped: the bar count stays roughly constant and only its meaning changes,
 *  which the axis labels state. */
function series(
  teasers: LibraryTeaser[],
  days: RangeDays,
): { label: string; value: number }[] {
  const bucketDays = days <= 7 ? 1 : days <= 30 ? 3 : 9;
  const buckets: { label: string; value: number }[] = [];
  const today = startOfDay(new Date());

  for (let offset = days - bucketDays; offset >= 0; offset -= bucketDays) {
    const from = new Date(today);
    from.setDate(today.getDate() - offset - (bucketDays - 1));
    const to = new Date(today);
    to.setDate(today.getDate() - offset + 1);

    const value = teasers.filter((teaser) => {
      const at = new Date(teaser.created_at).getTime();
      return at >= from.getTime() && at < to.getTime();
    }).length;

    buckets.push({
      label:
        bucketDays === 1
          ? from.toLocaleDateString("en-GB", { weekday: "short" })
          : from.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
      value,
    });
  }
  return buckets;
}

export default function DashboardScreen({ onOpenRun }: Props) {
  const state = useAsync<Totals>(async () => {
    const [jobs, teasers] = await Promise.all([listJobs(), listTeasers()]);
    return { jobs: jobs.jobs, teasers: teasers.teasers };
  }, []);

  const [days, setDays] = useState<RangeDays>(7);

  return (
    <AsyncBoundary state={state}>
      {({ jobs, teasers }) =>
        jobs.length === 0 ? (
          <section className="card">
            <div className="card-header">
              <span className="icon-tile">
                <Icon name="chart-pie" size={15} strokeWidth={2.2} />
              </span>
              <h2>Dashboard</h2>
            </div>
            <p className="empty-note">
              No runs recorded yet. Generate a set of teasers and this dashboard
              will summarise them.
            </p>
          </section>
        ) : (
          <Summary
            jobs={jobs}
            teasers={teasers}
            days={days}
            onDaysChange={setDays}
            onOpenRun={onOpenRun}
          />
        )
      }
    </AsyncBoundary>
  );
}

interface SummaryProps extends Totals, Props {
  days: RangeDays;
  onDaysChange: (days: RangeDays) => void;
}

function Summary({ jobs, teasers, days, onDaysChange, onOpenRun }: SummaryProps) {
  const cutoff = cutoffFor(days);

  // Everything below describes the selected window, not all time. Mixing the
  // two on one page is how a dashboard starts lying: a "success rate" over all
  // history next to a 7-day chart reads as a 7-day success rate.
  const windowJobs = useMemo(
    () => jobs.filter((job) => new Date(job.created_at).getTime() >= cutoff),
    [jobs, cutoff],
  );
  const windowTeasers = useMemo(
    () => teasers.filter((t) => new Date(t.created_at).getTime() >= cutoff),
    [teasers, cutoff],
  );

  const failed = windowJobs.filter((job) => job.status === "failed");
  const succeeded = windowJobs.filter((job) => job.status === "completed");
  const settled = failed.length + succeeded.length;
  const successRate = settled > 0 ? (succeeded.length / settled) * 100 : null;

  // The most common failure code, which is the one worth fixing first.
  const topFailure = useMemo(() => {
    const counts = new Map<string, number>();
    for (const job of failed) {
      const code = job.error_code ?? "UNKNOWN_ERROR";
      counts.set(code, (counts.get(code) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? null;
  }, [failed]);

  const averageScore =
    windowTeasers.length > 0
      ? windowTeasers.reduce((total, t) => total + t.score, 0) /
        windowTeasers.length
      : null;

  const totalClipSeconds = windowTeasers.reduce(
    (total, teaser) =>
      total + (teaser.duration_seconds ?? teaser.end_seconds - teaser.start_seconds),
    0,
  );

  // Per source rather than per audience: "which talk is producing the clips"
  // is the question a shelf of finished work actually raises.
  const byVideo = useMemo(() => {
    const counts = new Map<string, { label: string; value: number }>();
    for (const teaser of windowTeasers) {
      const row = counts.get(teaser.video_id);
      if (row) row.value += 1;
      else counts.set(teaser.video_id, { label: teaser.filename, value: 1 });
    }
    return [...counts.values()].sort((a, b) => b.value - a.value).slice(0, 6);
  }, [windowTeasers]);

  const bars = series(windowTeasers, days);
  const peak = Math.max(...bars.map((bucket) => bucket.value), 1);
  const activeIndex = bars.length - 1;

  return (
    <div id="dashboard">
      <div className="pagehead-controls">
        <div className="segmented segmented-sm" role="group" aria-label="Time range">
          {RANGES.map((range) => (
            <button
              key={range.days}
              type="button"
              className={`segment${days === range.days ? " segment-active" : ""}`}
              aria-pressed={days === range.days}
              onClick={() => onDaysChange(range.days)}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid">
        <section className="card">
          <div className="card-header">
            <span className="icon-tile">
              <Icon name="chart-pie" size={15} strokeWidth={2.2} />
            </span>
            <h2>Teasers Generated</h2>
          </div>
          <div className="stat-figure o-num">{windowTeasers.length}</div>
          <div className="stat-caption">
            across {windowJobs.length} run{windowJobs.length === 1 ? "" : "s"} in
            the last {days} days
          </div>

          {byVideo.length > 0 && (
            <>
              <h3 className="subhead">By Source</h3>
              <div className="breakdown">
                {byVideo.map((row) => (
                  <div className="breakdown-row" key={row.label + row.value}>
                    <span className="breakdown-label" title={row.label}>
                      {row.label}
                    </span>
                    <span className="track">
                      <span
                        className="track-fill"
                        style={{
                          width: `${(row.value / windowTeasers.length) * 100}%`,
                        }}
                      />
                    </span>
                    <span className="breakdown-value o-num">{row.value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <div className="stack">
          <div className="stats stats-three">
            <section className="card">
              <div className="card-header">
                <span className="icon-tile">
                  <Icon name="target" size={15} strokeWidth={2.2} />
                </span>
                <h2>Average Score</h2>
              </div>
              <div className="stat-figure stat-figure-sm o-num">
                {averageScore === null ? "—" : averageScore.toFixed(1)}
              </div>
              <div className="stat-caption">across every clip</div>
            </section>

            <section className="card">
              <div className="card-header">
                <span className="icon-tile">
                  <Icon name="clock" size={15} strokeWidth={2.2} />
                </span>
                <h2>Clip Time</h2>
              </div>
              <div className="stat-figure stat-figure-sm o-num">
                {formatDuration(totalClipSeconds)}
              </div>
              <div className="stat-caption">total footage produced</div>
            </section>

            <section className="card">
              <div className="card-header">
                <span
                  className={`icon-tile${failed.length > 0 ? " icon-tile-danger" : ""}`}
                >
                  <Icon name="triangle-alert" size={15} strokeWidth={2.2} />
                </span>
                <h2>Success Rate</h2>
              </div>
              <div className="stat-figure stat-figure-sm o-num">
                {successRate === null ? "—" : `${Math.round(successRate)}%`}
              </div>
              <div className="stat-caption">
                {failed.length === 0
                  ? `${succeeded.length} of ${settled} runs succeeded`
                  : `${failed.length} failed of ${settled}`}
              </div>
              {topFailure && (
                <p className="stat-note">
                  Most common: <span className="alert-code">{topFailure[0]}</span>
                  {topFailure[1] > 1 && ` ×${topFailure[1]}`}
                </p>
              )}
            </section>
          </div>

          <section className="card">
            <div className="card-header">
              <span className="icon-tile">
                <Icon name="chart-no-axes-column" size={15} strokeWidth={2.2} />
              </span>
              <h2>Overview</h2>
              <div className="card-header-actions">
                <span className="legend">
                  <span className="legend-swatch" />
                  Teasers
                </span>
                <span className="badge">Last {days} days</span>
              </div>
            </div>

            <div className="chart">
              <div className="chart-ticks o-num">
                <span>{peak}</span>
                <span>{Math.round(peak / 2)}</span>
                <span>0</span>
              </div>
              <div className="chart-plot">
                <div className="chart-grid">
                  <span />
                  <span />
                  <span />
                </div>
                <div className="chart-bars">
                  {bars.map((bucket, index) => (
                    <div className="bar-slot" key={bucket.label + index}>
                      <div className="bar-track">
                        <div
                          className={`bar${index === activeIndex ? " bar-active" : ""}`}
                          style={{
                            height: `${Math.max(2, (bucket.value / peak) * 100)}%`,
                          }}
                          title={`${bucket.value} clip${bucket.value === 1 ? "" : "s"}`}
                        />
                      </div>
                      <span
                        className={`bar-label${index === activeIndex ? " bar-label-active" : ""}`}
                      >
                        {bucket.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <section className="card">
        <div className="card-header">
          <span className="icon-tile">
            <Icon name="arrow-up-down" size={15} strokeWidth={2.2} />
          </span>
          <h2>Recent Runs</h2>
        </div>

        {windowJobs.length === 0 ? (
          <p className="empty-note">No runs in the last {days} days.</p>
        ) : (
          <div className="table">
            <div className="table-head">
              <span>Activity</span>
              <span>Date</span>
              <span>Clips</span>
              <span>Score</span>
              <span>Status</span>
            </div>
            {windowJobs.slice(0, 8).map((job) => {
              const clips = windowTeasers.filter((t) => t.job_id === job.job_id);
              const mean =
                clips.length > 0
                  ? clips.reduce((total, clip) => total + clip.score, 0) /
                    clips.length
                  : null;

              return (
                <button
                  type="button"
                  className="table-row table-row-button"
                  key={job.job_id}
                  onClick={() => onOpenRun(job)}
                >
                  <span className="cell-activity">
                    <span className="icon-tile icon-tile-neutral icon-tile-sm">
                      <Icon name="film" size={12} strokeWidth={2.2} />
                    </span>
                    <span className="cell-name">{job.filename}</span>
                  </span>
                  <span className="cell-muted o-num">{formatDate(job.created_at)}</span>
                  <span className="o-num">{job.teaser_count}</span>
                  <span className="o-num">{mean === null ? "—" : mean.toFixed(1)}</span>
                  <span>
                    <span
                      className={`status${job.status === "failed" ? " status-failed" : ""}`}
                      title={job.error_code ?? undefined}
                    >
                      <span className="status-dot" />
                      {job.status === "failed" ? "Failed" : "Success"}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
