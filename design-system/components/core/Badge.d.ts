import * as React from 'react';

/** Tiny tinted pill for month-over-month deltas on stat cards
 *  ("+3.2% ↑", "-2.1% ↓") and for counts. */
export interface BadgeProps {
  tone?: 'positive' | 'negative' | 'warning' | 'neutral' | 'brand';
  /** Draws a trailing ↑ / ↓ after the label. */
  arrow?: 'up' | 'down';
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function Badge(props: BadgeProps): JSX.Element;
