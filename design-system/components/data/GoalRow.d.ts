import * as React from 'react';

/** A savings-plan row: white icon tile + goal name, "$15,600/$25,000" with
 *  the percentage flush right, and a 5px progress track. */
export interface GoalRowProps {
  icon?: React.ReactNode;
  title: string;
  current: string;
  target: string;
  /** 0–100; drives both the label and the fill width. */
  percent: number;
  tone?: 'brand' | 'amber';
  style?: React.CSSProperties;
}
export declare function GoalRow(props: GoalRowProps): JSX.Element;
