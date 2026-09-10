import {
  DEGRADED_LABELS,
  DROP_REASON_LABELS,
  type JobResponse,
} from "../types";
import Icon from "../ui/Icon";

interface Props {
  job: JobResponse;
}

/** Percentage with no decimal places. Drop rates are read at a glance and
 *  "62%" carries every bit as much as "61.5%" does. */
function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/**
 * What the run threw away, and how cleanly it cut what it kept.
 *
 * The pipeline has always discarded candidates and always been right to. What
 * it has never done is say so anywhere the user can see, which made a run that
 * proposed eight moments and kept one indistinguishable from a run that kept
 * all eight — both showed the same "Generated 1 teaser".
 *
 * Rendered as a plain table rather than a chart. These are small integers a
 * reader compares against each other, and a chart of seven bars adds a legend
 * without adding a fact.
 *
 * Absent, not empty, on runs from before the report existed: an empty panel
 * headed "Nothing was discarded" would be a claim, and the truthful statement
 * about those runs is that nobody counted.
 */
export default function RunReportPanel({ job }: Props) {
  const report = job.pipeline_report;
  if (!report) return null;

  const { candidates, snap, degraded, clean_cut_rate: cleanCutRate } = report;
  const dropped = Object.entries(candidates.dropped ?? {}).filter(
    ([, count]) => count > 0,
  );
  const measuredCuts = report.cuts?.length ?? 0;
  // Every boundary that was actually offered a pause to move onto. Zero means
  // snapping never ran — no audio, or no silences found — which is a different
  // statement from "it ran and declined", and the panel must not merge them.
  const snapConsidered =
    (snap.starts_moved ?? 0) +
    (snap.starts_kept ?? 0) +
    (snap.ends_moved ?? 0) +
    (snap.ends_kept ?? 0);

  return (
    <section className="card">
      <div className="card-header">
        <span className="icon-tile">
          <Icon name="chart-no-axes-column" size={15} strokeWidth={2.2} />
        </span>
        <h2>What this run discarded</h2>
        <div className="card-header-actions">
          <span className="badge o-num" title="Share of proposed moments that were dropped">
            {percent(candidates.drop_rate ?? 0)} dropped
          </span>
        </div>
      </div>

      <p className="report-lede">
        The model proposed <strong className="o-num">{candidates.proposed ?? 0}</strong>{" "}
        moment{candidates.proposed === 1 ? "" : "s"};{" "}
        <strong className="o-num">{candidates.kept ?? 0}</strong> survived every check
        and the ranking.
      </p>

      {dropped.length > 0 && (
        <ul className="report-rows">
          {dropped.map(([reason, count]) => (
            <li key={reason}>
              {/* Falls back to the raw slug: a reason added on the server
                  should be visible here before anyone updates the label map. */}
              <span>{DROP_REASON_LABELS[reason] ?? reason}</span>
              <span className="o-num">{count}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="report-stats">
        <div>
          <span className="report-stat-label">Cut points moved onto a pause</span>
          <span className="report-stat-value o-num">
            {snapConsidered === 0
              ? "not attempted"
              : `${percent(snap.move_rate ?? 0)} of ${snapConsidered}`}
          </span>
        </div>
        <div>
          <span className="report-stat-label" title="Clips whose opening is quieter than the clip's own average, measured rather than judged">
            Clips that open on a pause
          </span>
          <span className="report-stat-value o-num">
            {measuredCuts === 0
              ? "not measured"
              : `${percent(cleanCutRate)} of ${measuredCuts}`}
          </span>
        </div>
      </div>

      {degraded.length > 0 && (
        <div className="report-degraded">
          <span className="report-stat-label">Carried on without</span>
          <ul>
            {degraded.map((tag) => (
              <li key={tag}>{DEGRADED_LABELS[tag] ?? tag}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
