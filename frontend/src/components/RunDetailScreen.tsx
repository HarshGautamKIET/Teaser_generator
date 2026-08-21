import { getTeasers } from "../api";
import { useAsync } from "../async";
import { formatDateTime } from "../format";
import { STATUS_LABELS, type JobSummary } from "../types";
import Icon from "../ui/Icon";
import AsyncBoundary from "./AsyncBoundary";
import TeaserCard from "./TeaserCard";

interface Props {
  job: JobSummary;
  onBack: () => void;
}

/** One run, in full.
 *
 *  Everything here was already persisted and never shown: which provider ran
 *  the analysis, the error code behind a failure, and the per-dimension scores
 *  that the single headline number is a mean of. A run that failed is the case
 *  this page is most needed for, so it reports the failure rather than an
 *  empty clip grid.
 */
export default function RunDetailScreen({ job, onBack }: Props) {
  // Scoped to this job explicitly: without it the backend answers with the
  // latest completed run, which for an older or failed run is another run's work.
  const state = useAsync(() => getTeasers(job.video_id, job.job_id), [job.job_id]);

  return (
    <>
      <section className="card">
        <div className="card-header">
          <button
            type="button"
            className="icon-btn"
            aria-label="Back to runs"
            title="Back to runs"
            onClick={onBack}
          >
            <Icon name="arrow-left" size={16} />
          </button>
          <h2>{job.filename}</h2>
          <div className="card-header-actions">
            <span className="badge badge-brand">
              {job.audience.replace("_", " ")} · {job.style}
            </span>
            <span
              className={`status${job.status === "failed" ? " status-failed" : ""}${
                job.status !== "failed" &&
                job.status !== "completed" &&
                job.status !== "cancelled"
                  ? " status-pending"
                  : ""
              }`}
            >
              <span className="status-dot" />
              {STATUS_LABELS[job.status]}
            </span>
          </div>
        </div>

        <dl className="facts">
          <div className="fact">
            <dt>Started</dt>
            <dd className="o-num">{formatDateTime(job.created_at)}</dd>
          </div>
          <div className="fact">
            <dt>Finished</dt>
            <dd className="o-num">
              {job.completed_at ? formatDateTime(job.completed_at) : "—"}
            </dd>
          </div>
          <div className="fact">
            <dt>Clips</dt>
            <dd className="o-num">
              {job.teaser_count}
              <span className="fact-sub"> · {job.aspect_ratio ?? "default"}</span>
            </dd>
          </div>
          <div className="fact">
            <dt>Analysed by</dt>
            <dd>{job.ai_provider ?? "—"}</dd>
          </div>
        </dl>

        {job.custom_prompt && (
          <div className="run-direction">
            <span className="run-direction-label">Direction given</span>
            <p>“{job.custom_prompt}”</p>
          </div>
        )}

        {job.status === "failed" && (
          <div className="alert" role="alert">
            <span className="icon-tile icon-tile-danger">
              <Icon name="triangle-alert" size={15} strokeWidth={2.2} />
            </span>
            <div className="alert-text">
              <div className="alert-message">
                {job.error_message ?? "This run failed without a recorded reason."}
              </div>
              <span className="alert-code">{job.error_code ?? "UNKNOWN_ERROR"}</span>
            </div>
          </div>
        )}
      </section>

      <AsyncBoundary state={state}>
        {({ teasers }) =>
          teasers.length === 0 ? (
            <section className="card">
              <p className="empty-note">
                {job.status === "failed"
                  ? "This run produced no clips."
                  : job.status === "cancelled"
                    ? "This run was cancelled before it produced any clips."
                    : "No clips are recorded against this run yet."}
              </p>
            </section>
          ) : (
            <section className="card">
              <div className="card-header">
                <span className="icon-tile">
                  <Icon name="layout-grid" size={15} strokeWidth={2.2} />
                </span>
                <h2>Clips</h2>
                <div className="card-header-actions">
                  <span className="badge o-num">{teasers.length}</span>
                </div>
              </div>
              <div className="teaser-grid">
                {teasers.map((teaser) => (
                  <TeaserCard key={teaser.id} teaser={teaser} />
                ))}
              </div>
            </section>
          )
        }
      </AsyncBoundary>
    </>
  );
}
