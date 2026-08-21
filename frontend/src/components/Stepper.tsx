import Icon, { type IconName } from "../ui/Icon";

export type StepId = "source" | "options" | "processing" | "teasers";

export interface Step {
  id: StepId;
  label: string;
  icon: IconName;
  /** Reached at least once, so it can be navigated to. */
  enabled: boolean;
  /** Its work is actually finished. Not the same as "earlier in the list":
   *  visiting a step then moving on does not complete it. */
  complete?: boolean;
  /** Why it cannot be opened yet, shown on hover. */
  blockedReason?: string;
  count?: number;
}

interface Props {
  steps: Step[];
  current: StepId;
  onSelect: (id: StepId) => void;
}

/** Progress through the generation flow, and the only way to move between its
 *  screens.
 *
 *  This replaced a second sidebar nav group that duplicated "Generate" and
 *  merely scrolled the page: two controls that looked like destinations, went
 *  to the same place, and showed an active state derived from app state rather
 *  than from what was clicked. Position in a linear flow is progress, not
 *  site structure, so it belongs on the page and not in the sidebar. */
export default function Stepper({ steps, current, onSelect }: Props) {
  return (
    <nav className="stepper" aria-label="Generation progress">
      <ol className="stepper-list">
        {steps.map((step, index) => {
          const isCurrent = step.id === current;
          const isDone = step.complete === true;
          const state = isCurrent ? "current" : isDone ? "done" : "todo";

          return (
            <li className={`stepper-item stepper-item-${state}`} key={step.id}>
              <button
                type="button"
                className="stepper-btn"
                disabled={!step.enabled}
                aria-current={isCurrent ? "step" : undefined}
                title={step.enabled ? undefined : step.blockedReason}
                onClick={() => onSelect(step.id)}
              >
                <span className="stepper-marker">
                  {isDone ? (
                    <Icon name="check" size={13} strokeWidth={2.6} />
                  ) : (
                    <Icon name={step.icon} size={14} strokeWidth={2.2} />
                  )}
                </span>
                <span className="stepper-text">
                  <span className="stepper-index o-num">Step {index + 1}</span>
                  <span className="stepper-label">
                    {step.label}
                    {step.count !== undefined && (
                      <span className="stepper-count o-num">{step.count}</span>
                    )}
                  </span>
                </span>
              </button>
              {index < steps.length - 1 && (
                <span className="stepper-line" aria-hidden="true" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
