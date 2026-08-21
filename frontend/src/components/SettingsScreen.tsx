import { listTeasers, listVideos } from "../api";
import { useAsync } from "../async";
import { formatSize } from "../format";
import {
  CLIP_SECONDS_RANGE,
  TEASER_COUNT_RANGE,
  type Preferences,
} from "../preferences";
import {
  ASPECT_RATIO_OPTIONS,
  AUDIENCE_OPTIONS,
  STYLE_OPTIONS,
  type AspectRatio,
  type Audience,
  type Style,
} from "../types";
import Icon from "../ui/Icon";

interface Props {
  email: string | null;
  preferences: Preferences;
  onPreferencesChange: (preferences: Preferences) => void;
  onSignOut: () => void;
}

/** Account facts, generation defaults, and the pipeline knobs.
 *
 *  Teaser count and clip length used to be environment variables, which meant
 *  changing either needed a redeploy and applied to everyone on the deployment.
 *  They are sent per run now, so this screen is where they actually live.
 */
export default function SettingsScreen({
  email,
  preferences,
  onPreferencesChange,
  onSignOut,
}: Props) {
  const usage = useAsync(async () => {
    const [videos, teasers] = await Promise.all([listVideos(), listTeasers()]);
    return {
      sourceBytes: videos.videos.reduce((total, v) => total + v.size_bytes, 0),
      clipBytes: teasers.teasers.reduce((total, t) => total + t.size_bytes, 0),
      videoCount: videos.videos.length,
      clipCount: teasers.teasers.length,
    };
  }, []);

  const set = <K extends keyof Preferences>(key: K, value: Preferences[K]) =>
    onPreferencesChange({ ...preferences, [key]: value });

  return (
    <>
      <section className="card">
        <div className="card-header">
          <span className="icon-tile">
            <Icon name="mail" size={15} strokeWidth={2.2} />
          </span>
          <h2>Account</h2>
        </div>

        <dl className="facts">
          <div className="fact">
            <dt>Signed in as</dt>
            <dd>{email ?? "Unknown"}</dd>
          </div>
          <div className="fact">
            <dt>Storage used</dt>
            <dd className="o-num">
              {usage.data
                ? formatSize(usage.data.sourceBytes + usage.data.clipBytes)
                : "—"}
            </dd>
          </div>
          <div className="fact">
            <dt>Source videos</dt>
            <dd className="o-num">
              {usage.data ? usage.data.videoCount : "—"}
              {usage.data && (
                <span className="fact-sub"> · {formatSize(usage.data.sourceBytes)}</span>
              )}
            </dd>
          </div>
          <div className="fact">
            <dt>Generated clips</dt>
            <dd className="o-num">
              {usage.data ? usage.data.clipCount : "—"}
              {usage.data && (
                <span className="fact-sub"> · {formatSize(usage.data.clipBytes)}</span>
              )}
            </dd>
          </div>
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <span className="icon-tile">
            <Icon name="cpu" size={15} strokeWidth={2.2} />
          </span>
          <h2>Pipeline</h2>
        </div>
        <p className="empty-note settings-note">
          How much each run produces. Sent with every generation request, so a
          change applies to the next run.
        </p>

        <div className="slider-row">
          <div className="slider-head">
            <label className="field-label" htmlFor="teaser-count">
              Teasers per run
            </label>
            <span className="slider-value o-num">{preferences.teaserCount}</span>
          </div>
          <input
            id="teaser-count"
            className="slider"
            type="range"
            min={TEASER_COUNT_RANGE.min}
            max={TEASER_COUNT_RANGE.max}
            step={1}
            value={preferences.teaserCount}
            onChange={(event) => set("teaserCount", Number(event.target.value))}
          />
          <p className="field-hint">
            The pipeline keeps the best moments it found. Asking for more than
            the video contains simply yields fewer.
          </p>
        </div>

        <div className="slider-row">
          <div className="slider-head">
            <label className="field-label" htmlFor="clip-length">
              Maximum clip length
            </label>
            <span className="slider-value o-num">{preferences.clipMaxSeconds}s</span>
          </div>
          <input
            id="clip-length"
            className="slider"
            type="range"
            min={CLIP_SECONDS_RANGE.min}
            max={CLIP_SECONDS_RANGE.max}
            step={5}
            value={preferences.clipMaxSeconds}
            onChange={(event) => set("clipMaxSeconds", Number(event.target.value))}
          />
          <p className="field-hint">
            Moments longer than this are discarded rather than trimmed, so a very
            short ceiling can leave a run with nothing to cut.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <span className="icon-tile">
            <Icon name="sparkles" size={15} strokeWidth={2.2} />
          </span>
          <h2>Generation Defaults</h2>
        </div>
        <p className="empty-note settings-note">
          What a new run starts with. Kept in this browser, and changeable per
          run — this only decides the starting point.
        </p>

        <fieldset className="choice-group">
          <legend className="choice-legend">Default audience</legend>
          <div className="choice-grid">
            {AUDIENCE_OPTIONS.map((option) => (
              <label
                key={option.value}
                className={`choice${
                  preferences.audience === option.value ? " choice-selected" : ""
                }`}
              >
                <input
                  type="radio"
                  name="default-audience"
                  value={option.value}
                  checked={preferences.audience === option.value}
                  onChange={() => set("audience", option.value as Audience)}
                />
                <span className="choice-label">{option.label}</span>
                <span className="choice-blurb">{option.blurb}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="choice-group">
          <legend className="choice-legend">Default output format</legend>
          <div className="ratio-grid">
            {ASPECT_RATIO_OPTIONS.map((option) => (
              <label
                key={option.value}
                className={`choice ratio-choice${
                  preferences.aspectRatio === option.value ? " choice-selected" : ""
                }`}
              >
                <input
                  type="radio"
                  name="default-aspect-ratio"
                  value={option.value}
                  checked={preferences.aspectRatio === option.value}
                  onChange={() => set("aspectRatio", option.value as AspectRatio)}
                />
                <span className="ratio-preview" aria-hidden="true">
                  <span
                    className="ratio-box"
                    style={{
                      width: `${option.frame.width}px`,
                      height: `${option.frame.height}px`,
                    }}
                  />
                </span>
                <span className="choice-label">
                  {option.label}
                  <span className="ratio-value o-num">{option.value}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="choice-group">
          <legend className="choice-legend">Default style</legend>
          <div className="choice-grid">
            {STYLE_OPTIONS.map((option) => (
              <label
                key={option.value}
                className={`choice${
                  preferences.style === option.value ? " choice-selected" : ""
                }`}
              >
                <input
                  type="radio"
                  name="default-style"
                  value={option.value}
                  checked={preferences.style === option.value}
                  onChange={() => set("style", option.value as Style)}
                />
                <span className="choice-label">{option.label}</span>
                <span className="choice-blurb">{option.blurb}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      {/* Sign out sits on its own, below everything else: it ends the session,
          and does not belong beside controls that only adjust a slider. */}
      <section className="card">
        <div className="card-header">
          <span className="icon-tile">
            <Icon name="log-out" size={15} strokeWidth={2.2} />
          </span>
          <h2>Session</h2>
        </div>
        <div className="card-footer-actions">
          <span className="cell-muted">
            Signing out leaves your videos and clips untouched.
          </span>
          <button type="button" className="btn btn-outline btn-sm" onClick={onSignOut}>
            <Icon name="log-out" size={13} />
            Sign out
          </button>
        </div>
      </section>
    </>
  );
}
