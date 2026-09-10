import {
  ASPECT_RATIO_OPTIONS,
  AUDIENCE_OPTIONS,
  MAX_CUSTOM_PROMPT_CHARS,
  RECORDING_TYPE_OPTIONS,
  STYLE_OPTIONS,
  type AspectRatio,
  type Audience,
  type RecordingType,
  type Style,
} from "../types";
import Icon from "../ui/Icon";

interface Props {
  audience: Audience;
  style: Style;
  aspectRatio: AspectRatio;
  recordingType: RecordingType;
  customPrompt: string;
  onAudienceChange: (value: Audience) => void;
  onStyleChange: (value: Style) => void;
  onAspectRatioChange: (value: AspectRatio) => void;
  onRecordingTypeChange: (value: RecordingType) => void;
  onCustomPromptChange: (value: string) => void;
  disabled: boolean;
}

export default function OptionsPanel({
  audience,
  style,
  aspectRatio,
  recordingType,
  customPrompt,
  onAudienceChange,
  onStyleChange,
  onAspectRatioChange,
  onRecordingTypeChange,
  onCustomPromptChange,
  disabled,
}: Props) {
  const remaining = MAX_CUSTOM_PROMPT_CHARS - customPrompt.length;
  return (
    <section className="card" id="options">
      <div className="card-header">
        <span className="icon-tile">
          <Icon name="users" size={15} strokeWidth={2.2} />
        </span>
        <h2>Audience &amp; Style</h2>
      </div>

      {/* First, because it describes the video rather than the output, and it
          changes what the rest of this panel produces: how self-contained a
          moment has to be, how far apart clips are spaced, and whether the
          frame is cropped or padded to reach the shape chosen below. */}
      <fieldset className="choice-group" disabled={disabled}>
        <legend className="choice-legend">What kind of recording is this?</legend>
        <div className="choice-grid">
          {RECORDING_TYPE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className={`choice${
                recordingType === option.value ? " choice-selected" : ""
              }`}
            >
              <input
                type="radio"
                name="recording-type"
                value={option.value}
                checked={recordingType === option.value}
                onChange={() => onRecordingTypeChange(option.value)}
              />
              <span className="choice-label">{option.label}</span>
              <span className="choice-blurb">{option.blurb}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="choice-group" disabled={disabled}>
        <legend className="choice-legend">Target Audience</legend>
        <div className="choice-grid">
          {AUDIENCE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className={`choice${audience === option.value ? " choice-selected" : ""}`}
            >
              <input
                type="radio"
                name="audience"
                value={option.value}
                checked={audience === option.value}
                onChange={() => onAudienceChange(option.value)}
              />
              <span className="choice-label">{option.label}</span>
              <span className="choice-blurb">{option.blurb}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="choice-group" disabled={disabled}>
        <legend className="choice-legend">Teaser Style</legend>
        <div className="choice-grid">
          {STYLE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className={`choice${style === option.value ? " choice-selected" : ""}`}
            >
              <input
                type="radio"
                name="style"
                value={option.value}
                checked={style === option.value}
                onChange={() => onStyleChange(option.value)}
              />
              <span className="choice-label">{option.label}</span>
              <span className="choice-blurb">{option.blurb}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="choice-group" disabled={disabled}>
        <legend className="choice-legend">
          What should it look for?
          <span className="choice-legend-optional">Optional</span>
        </legend>
        {/* Narrows selection inside the audience and style above rather than
            replacing them, so those two controls keep meaning what they say. */}
        <div className="field">
          <textarea
            id="custom-prompt"
            className="input textarea"
            rows={3}
            maxLength={MAX_CUSTOM_PROMPT_CHARS}
            placeholder="e.g. Focus on the live demo and the pricing discussion. Skip the intro."
            value={customPrompt}
            disabled={disabled}
            onChange={(event) => onCustomPromptChange(event.target.value)}
          />
          <div className="field-footer">
            <p className="field-hint">
              Steers which moments get picked. The audience and style above
              still apply.
            </p>
            <span
              className={`char-count o-num${remaining < 50 ? " char-count-low" : ""}`}
            >
              {remaining}
            </span>
          </div>
        </div>
      </fieldset>

      <fieldset className="choice-group" disabled={disabled}>
        <legend className="choice-legend">Output Format</legend>
        {/* Each option carries a preview box in its own proportions. The shape
            is the thing being chosen, so showing it beats naming it. */}
        <div className="ratio-grid">
          {ASPECT_RATIO_OPTIONS.map((option) => (
            <label
              key={option.value}
              className={`choice ratio-choice${
                aspectRatio === option.value ? " choice-selected" : ""
              }`}
            >
              <input
                type="radio"
                name="aspect-ratio"
                value={option.value}
                checked={aspectRatio === option.value}
                onChange={() => onAspectRatioChange(option.value)}
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
              <span className="choice-blurb">{option.blurb}</span>
            </label>
          ))}
        </div>
        {/* Said here rather than in the recording-type group above, because
            this is where the consequence shows up: a demo cut to 9:16 comes
            back with bars, and that is a deliberate trade rather than a bug to
            report. */}
        {recordingType !== "webinar" && (
          <p className="field-hint">
            Screen content is fitted inside the frame rather than cropped to
            fill it, so on-screen text stays readable. Shapes narrower than the
            source will have bars.
          </p>
        )}
      </fieldset>
    </section>
  );
}
