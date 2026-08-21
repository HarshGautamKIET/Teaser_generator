import * as React from 'react';

/** Headline metric card: icon tile + title, one extrabold tabular figure,
 *  then a delta Badge with "from last month" beside it.
 *
 * @startingPoint section="Data" subtitle="Metric card with month-over-month delta" viewport="700x210"
 */
export interface StatCardProps {
  icon?: React.ReactNode;
  title: string;
  value: string;
  /** e.g. "+3.2%" — omit to hide the delta row entirely. */
  delta?: string | null;
  deltaTone?: 'positive' | 'negative' | 'warning' | 'neutral' | 'brand';
  deltaArrow?: 'up' | 'down';
  caption?: string;
  actions?: React.ReactNode;
  /** Extra content below the delta (Account Balance adds the send/request buttons). */
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function StatCard(props: StatCardProps): JSX.Element;
