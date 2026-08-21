import type { ReactNode } from "react";

import type { AsyncState } from "../async";
import Icon from "../ui/Icon";

interface Props<T> {
  state: AsyncState<T>;
  children: (data: T) => ReactNode;
}

/** The loading and failure states every listing page owes its reader.
 *
 *  A failed fetch renders as a failure with a way out, not as an empty list:
 *  "you have no clips" and "we could not ask" look identical otherwise, and
 *  only one of them is the reader's fault to fix.
 *
 *  Children are a function rather than nodes so the loaded data is non-null by
 *  the time a page renders it, instead of every page guarding for a value this
 *  component has already established is there.
 */
export default function AsyncBoundary<T>({ state, children }: Props<T>) {
  if (state.error) {
    return (
      <section className="card">
        <div className="card-header">
          <span className="icon-tile icon-tile-danger">
            <Icon name="triangle-alert" size={15} strokeWidth={2.2} />
          </span>
          <h2>Could not load</h2>
        </div>
        <p className="empty-note">{state.error.message}</p>
        <div className="card-footer-actions">
          <span className="alert-code">{state.error.code}</span>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={state.reload}
          >
            <Icon name="refresh-cw" size={13} />
            Try again
          </button>
        </div>
      </section>
    );
  }

  // Keyed on data rather than `loading`, so a refresh leaves the current page on
  // screen instead of blanking something the reader is in the middle of using.
  if (state.data === null) {
    return (
      <section className="card">
        <p className="empty-note">Loading…</p>
      </section>
    );
  }

  return <>{children(state.data)}</>;
}
