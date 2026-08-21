import { STATUS_LABELS, type JobResponse, type JobStatus } from "../types";
import Icon from "../ui/Icon";

/** The stages a job passes through, in order (FR-018). */
const STAGES: JobStatus[] = [
  "queued",
  "validating",
  "analyzing",
  "ranking",
  "generating",
  "completed",
];

interface Props {
  job: JobResponse;
}

export default function ProgressPanel({ job }: Props) {
  const failed = job.status === "failed";
  const done = job.status === "completed";
  const currentIndex = STAGES.indexOf(job.status);

  return (
    <section className="card" id="processing">
      <div className="card-header">
        <span className={`icon-tile${failed ? " icon-tile-danger" : ""}`}>
          <Icon name="layers" size={15} strokeWidth={2.2} />
        </span>
        <h2>Processing</h2>
        <div className="card-header-actions">
          <span
            className={`status${failed ? " status-failed" : done ? "" : " status-pending"}`}
          >
            <span className="status-dot" />
            {failed ? "Failed" : done ? "Completed" : "Running"}
          </span>
        </div>
      </div>

      <div className="progress-head">
        <span className="progress-stage">
          {failed ? "Failed" : STATUS_LABELS[job.status]}
        </span>
        <span className="progress-percent o-num">{job.progress}%</span>
      </div>

      <div className="track">
        <div
          className={`track-fill${failed ? " track-fill-failed" : ""}`}
          style={{ width: `${failed ? 100 : job.progress}%` }}
        />
      </div>

      <p className="progress-message">{job.message}</p>

      <ol className="stages">
        {STAGES.filter((stage) => stage !== "completed").map((stage) => {
          const index = STAGES.indexOf(stage);
          const complete = !failed && currentIndex > index;
          const active = !failed && currentIndex === index;
          return (
            <li
              key={stage}
              className={`stage${complete ? " stage-done" : ""}${active ? " stage-active" : ""}`}
            >
              <span className="stage-dot" aria-hidden="true" />
              {STATUS_LABELS[stage]}
            </li>
          );
        })}
      </ol>

      {job.ai_provider && (
        <p className="provider-note">
          Analysed by <code>{job.ai_provider}</code>
        </p>
      )}
    </section>
  );
}
