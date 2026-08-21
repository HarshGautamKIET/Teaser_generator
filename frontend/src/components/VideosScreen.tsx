import { listVideos } from "../api";
import { useAsync } from "../async";
import { formatDate, formatDuration, formatSize } from "../format";
import type { VideoSummary } from "../types";
import Icon from "../ui/Icon";
import AsyncBoundary from "./AsyncBoundary";

/** Just the host, so a long watch URL does not push the table wide. The full
 *  URL stays available as a tooltip. */
function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

interface Props {
  /** Make this video the active source and go to the audience step. */
  onGenerate: (video: VideoSummary) => void;
  /** Show only this video's runs on the Runs page. */
  onOpenRuns: (videoId: string) => void;
  onUpload: () => void;
}

/** Sources already uploaded.
 *
 *  This page exists because a video was previously reachable only for as long
 *  as the tab remembered it: re-running the same talk for a second audience
 *  meant uploading the file again. Every row here is a source the backend
 *  already holds, so "Generate" is one request rather than another upload.
 */
export default function VideosScreen({ onGenerate, onOpenRuns, onUpload }: Props) {
  const state = useAsync(listVideos, []);

  return (
    <AsyncBoundary state={state}>
      {({ videos }) =>
        videos.length === 0 ? (
          <section className="card">
            <div className="card-header">
              <span className="icon-tile">
                <Icon name="video" size={15} strokeWidth={2.2} />
              </span>
              <h2>Videos</h2>
            </div>
            <p className="empty-note">
              No source videos yet. Upload one and it stays here — you can
              generate from it again for a different audience without
              re-uploading.
            </p>
            <div className="card-footer-actions">
              <button type="button" className="btn btn-primary btn-sm" onClick={onUpload}>
                <Icon name="upload" size={13} />
                Upload a video
              </button>
            </div>
          </section>
        ) : (
          <section className="card">
            <div className="card-header">
              <span className="icon-tile">
                <Icon name="video" size={15} strokeWidth={2.2} />
              </span>
              <h2>Videos</h2>
              <div className="card-header-actions">
                <span className="badge o-num">{videos.length}</span>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={onUpload}
                >
                  <Icon name="upload" size={13} />
                  Upload
                </button>
              </div>
            </div>

            <div className="table table-videos">
              <div className="table-head">
                <span>Source</span>
                <span>Uploaded</span>
                <span>Length</span>
                <span>Size</span>
                <span>Runs</span>
                <span>Clips</span>
                <span />
              </div>

              {videos.map((video) => (
                <div className="table-row" key={video.video_id}>
                  <span className="cell-activity">
                    <span className="icon-tile icon-tile-neutral icon-tile-sm">
                      <Icon
                        name={video.source_type === "url" ? "link" : "film"}
                        size={12}
                        strokeWidth={2.2}
                      />
                    </span>
                    <span className="cell-stacked">
                      <span className="cell-name">{video.filename}</span>
                      <span className="cell-sub o-num">
                        {video.source_type === "url" && video.source_url ? (
                          <span title={video.source_url}>{hostOf(video.source_url)}</span>
                        ) : (
                          video.width &&
                          video.height && `${video.width}×${video.height}`
                        )}
                      </span>
                    </span>
                  </span>

                  <span className="cell-muted o-num">{formatDate(video.created_at)}</span>
                  <span className="o-num">{formatDuration(video.duration_seconds)}</span>
                  <span className="cell-muted o-num">{formatSize(video.size_bytes)}</span>

                  <span className="o-num">
                    {video.job_count > 0 ? (
                      <button
                        type="button"
                        className="link-btn"
                        title="Show this video's runs"
                        onClick={() => onOpenRuns(video.video_id)}
                      >
                        {video.job_count}
                      </button>
                    ) : (
                      "0"
                    )}
                  </span>
                  <span className="o-num">{video.teaser_count}</span>

                  <span className="cell-actions">
                    {video.status === "ready" ? (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => onGenerate(video)}
                        title="Generate teasers from this source"
                      >
                        <Icon name="sparkles" size={13} />
                        Generate
                      </button>
                    ) : video.status === "failed" ? (
                      <span
                        className="status status-failed"
                        title={video.error_message ?? undefined}
                      >
                        <span className="status-dot" />
                        Failed
                      </span>
                    ) : (
                      <span className="status status-pending">
                        <span className="status-dot status-dot-pulse" />
                        Fetching
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )
      }
    </AsyncBoundary>
  );
}
