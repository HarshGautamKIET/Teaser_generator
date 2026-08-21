import { useRef, useState } from "react";

import { formatDuration, formatSize } from "../format";
import type { VideoResponse } from "../types";
import Icon from "../ui/Icon";

type Source = "file" | "url";

interface Props {
  video: VideoResponse | null;
  uploading: boolean;
  uploadPercent: number;
  /** True while a URL fetch is running server-side. */
  fetching: boolean;
  fetchStatus: string | null;
  onSelect: (file: File) => void;
  onSubmitUrl: (url: string) => void;
  disabled: boolean;
}

export default function UploadPanel({
  video,
  uploading,
  uploadPercent,
  fetching,
  fetchStatus,
  onSelect,
  onSubmitUrl,
  disabled,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [source, setSource] = useState<Source>("file");
  const [url, setUrl] = useState("");

  const pick = (files: FileList | null) => {
    if (files && files.length > 0) onSelect(files[0]);
  };

  const busy = uploading || fetching || disabled;

  if (video) {
    return (
      <section className="card" id="source">
        <div className="card-header">
          <span className="icon-tile">
            <Icon name={video.source_type === "url" ? "link" : "upload"} size={15} strokeWidth={2.2} />
          </span>
          <h2>Source Video</h2>
        </div>

        <div className="filename">{video.filename}</div>
        {video.source_url && (
          <p className="source-origin" title={video.source_url}>
            <Icon name="link" size={12} />
            {video.source_url}
          </p>
        )}

        <dl className="facts">
          <div className="fact">
            <dt>Length</dt>
            <dd className="o-num">{formatDuration(video.duration_seconds)}</dd>
          </div>
          <div className="fact">
            <dt>Size</dt>
            <dd className="o-num">{formatSize(video.size_bytes)}</dd>
          </div>
          <div className="fact">
            <dt>Resolution</dt>
            <dd className="o-num">
              {video.width && video.height
                ? `${video.width}×${video.height}`
                : "Unknown"}
            </dd>
          </div>
          <div className="fact">
            <dt>Frame Rate</dt>
            <dd className="o-num">
              {video.fps ? `${Math.round(video.fps)} fps` : "Unknown"}
            </dd>
          </div>
        </dl>

        <div className="card-footer-actions">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            <Icon name="plus" size={13} />
            Choose Another
          </button>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/x-matroska,video/webm,.mp4,.mov,.mkv,.webm"
          hidden
          onChange={(event) => {
            pick(event.target.files);
            event.target.value = "";
          }}
        />
      </section>
    );
  }

  return (
    <section className="card" id="source">
      <div className="card-header">
        <span className="icon-tile">
          <Icon name="upload" size={15} strokeWidth={2.2} />
        </span>
        <h2>Source Video</h2>
      </div>

      {/* Two ways in, presented as one choice rather than two competing panels.
          A long conference talk is usually already hosted somewhere, and making
          someone download it just to upload it again is the slow path. */}
      <div className="segmented" role="tablist" aria-label="Video source">
        <button
          type="button"
          role="tab"
          aria-selected={source === "file"}
          className={`segment${source === "file" ? " segment-active" : ""}`}
          disabled={busy}
          onClick={() => setSource("file")}
        >
          <Icon name="upload" size={14} />
          Upload a file
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={source === "url"}
          className={`segment${source === "url" ? " segment-active" : ""}`}
          disabled={busy}
          onClick={() => setSource("url")}
        >
          <Icon name="link" size={14} />
          From a link
        </button>
      </div>

      {source === "file" ? (
        <button
          type="button"
          disabled={busy}
          className={`dropzone${dragging ? " dropzone-active" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            if (!busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            if (!busy) pick(event.dataTransfer.files);
          }}
        >
          {uploading ? (
            <>
              <div className="dropzone-title o-num">Uploading {uploadPercent}%</div>
              <div className="track dropzone-progress">
                <div className="track-fill" style={{ width: `${uploadPercent}%` }} />
              </div>
            </>
          ) : (
            <>
              <div className="dropzone-title">Drop a Video Here</div>
              <div className="dropzone-hint">
                MP4, MOV, MKV or WebM — or click to browse
              </div>
            </>
          )}
        </button>
      ) : (
        <form
          className="url-form"
          onSubmit={(event) => {
            event.preventDefault();
            const trimmed = url.trim();
            if (trimmed && !busy) onSubmitUrl(trimmed);
          }}
        >
          <div className="field">
            <label className="field-label" htmlFor="source-url">
              Video URL
            </label>
            <div className="input-wrap">
              <input
                id="source-url"
                className="input"
                type="url"
                inputMode="url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                disabled={busy}
                onChange={(event) => setUrl(event.target.value)}
              />
            </div>
            <p className="field-hint">
              A YouTube, Vimeo, or direct video link. The server downloads it —
              nothing is uploaded from this device.
            </p>
          </div>

          {fetching ? (
            <div className="fetch-status" role="status">
              <span className="spinner" aria-hidden="true" />
              {/* Percentage would be a lie: the server reports a state, not a
                  byte count, so this says what is happening instead. */}
              {fetchStatus ?? "Fetching the video…"}
            </div>
          ) : (
            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={busy || url.trim().length === 0}
            >
              <Icon name="download" size={14} />
              Fetch Video
            </button>
          )}
        </form>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/x-matroska,video/webm,.mp4,.mov,.mkv,.webm"
        hidden
        onChange={(event) => {
          pick(event.target.files);
          event.target.value = "";
        }}
      />
    </section>
  );
}
