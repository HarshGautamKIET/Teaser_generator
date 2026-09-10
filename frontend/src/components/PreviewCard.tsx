import { formatSize } from "../format";
import type { JobResponse } from "../types";
import Icon from "../ui/Icon";
import { useAuthedMedia } from "../useMedia";

interface Props {
  job: JobResponse;
}

/** The run's assembled preview.
 *
 *  Distinct from the clips below it, and deliberately presented that way: every
 *  teaser is one moment cut to stand alone, while this is several moments joined
 *  with title cards — the one output allowed to be made of fragments, because
 *  the cards supply the context the fragments are missing.
 *
 *  Renders nothing when the run made no preview. A preview needs at least two
 *  moments, so a run that selected one has none, and that is ordinary rather
 *  than a failure worth reporting.
 */
export default function PreviewCard({ job }: Props) {
  const hasPreview = job.preview_url !== null;
  const { url, failed } = useAuthedMedia(hasPreview ? job.preview_url! : "");

  if (!hasPreview) return null;

  const seconds = job.preview_duration_seconds;

  return (
    <section className="card" id="preview">
      <div className="card-header">
        <span className="icon-tile">
          <Icon name="film" size={15} strokeWidth={2.2} />
        </span>
        <h2>Preview</h2>
        <div className="card-header-actions">
          {seconds !== null && (
            <span className="badge o-num">{seconds.toFixed(1)}s</span>
          )}
          {job.preview_size_bytes !== null && (
            <span className="badge o-num">
              {formatSize(job.preview_size_bytes)}
            </span>
          )}
        </div>
      </div>

      <p className="field-hint">
        One spot built from the strongest moments, joined with title cards —
        rather than a single excerpt.
      </p>

      {failed ? (
        <p className="empty-note">The preview could not be loaded.</p>
      ) : url ? (
        <div className="preview-video">
          <video src={url} controls preload="metadata" />
        </div>
      ) : (
        <p className="empty-note">Loading the preview…</p>
      )}

      <a
        className="btn btn-secondary btn-sm"
        href={url ?? undefined}
        aria-disabled={url === null}
        download="preview.mp4"
      >
        <Icon name="download" size={13} />
        Download MP4
      </a>
    </section>
  );
}
