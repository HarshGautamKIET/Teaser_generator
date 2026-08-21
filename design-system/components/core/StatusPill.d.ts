import * as React from 'react';

/** Transaction / wallet state label. Colour-only text with an optional
 *  filled dot; no background fill — that is what separates it from Badge. */
export interface StatusPillProps {
  tone?: 'success' | 'pending' | 'failed' | 'active' | 'inactive';
  /** Show the leading filled dot (transaction table). Wallet tiles omit it. */
  dot?: boolean;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function StatusPill(props: StatusPillProps): JSX.Element;
