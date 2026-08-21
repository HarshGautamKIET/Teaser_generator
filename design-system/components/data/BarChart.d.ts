import * as React from 'react';

/** Overview chart: pill-capped bars that fade to transparent at the
 *  baseline. Pale green at rest, saturated green plus a ringed dot and a
 *  white floating tooltip for the hovered/active month. */
export interface BarChartDatum { label: string; value: number }
export interface BarChartProps {
  data?: BarChartDatum[];
  /** Month highlighted before any hover. */
  activeIndex?: number;
  height?: number;
  /** Y-axis labels, top to bottom. */
  ticks?: string[];
  /** Floating readout for the active bar. */
  tooltip?: { label: string; value: string } | null;
  onHover?: (index: number) => void;
  style?: React.CSSProperties;
}
export declare function BarChart(props: BarChartProps): JSX.Element;
