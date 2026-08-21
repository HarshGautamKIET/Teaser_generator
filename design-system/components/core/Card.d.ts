import * as React from 'react';

/** The white 16px-radius panel every dashboard module lives in, plus its
 *  standard header row (icon tile + bold title + right-aligned actions).
 *
 * @startingPoint section="Core" subtitle="Card shell and card header row" viewport="700x220"
 */
export interface CardProps {
  children?: React.ReactNode;
  /** false removes the 18px interior padding (tables bleed to the edge). */
  pad?: boolean;
  style?: React.CSSProperties;
}
export interface CardHeaderProps {
  icon?: React.ReactNode;
  title: string;
  actions?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function Card(props: CardProps): JSX.Element;
export declare function CardHeader(props: CardHeaderProps): JSX.Element;
