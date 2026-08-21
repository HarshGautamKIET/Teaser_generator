import {
  ASPECT_RATIO_OPTIONS,
  AUDIENCE_OPTIONS,
  MAX_CUSTOM_PROMPT_CHARS,
  STYLE_OPTIONS,
  type AspectRatio,
  type Audience,
  type Style,
} from "../types";
import Icon from "../ui/Icon";

interface Props {
  audience: Audience;
  style: Style;
  aspectRatio: AspectRatio;
  customPrompt: string;
  onAudienceChange: (value: Audience) => void;
  onStyleChange: (value: Style) => void;
  onAspectRatioChange: (value: AspectRatio) => void;
  onCustomPromptChange: (value: string) => void;
  disabled: boolean;
}

export default function OptionsPanel({
  audience,
  style,
  aspectRatio,
  customPrompt,
  onAudienceChange,
  onStyleChange,
  onAspectRatioChange,
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
      </fieldset>
    </section>
  );
}
