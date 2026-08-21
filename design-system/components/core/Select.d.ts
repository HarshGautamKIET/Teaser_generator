import * as React from 'react';

/** Compact chevron dropdown used for card-scoped scope pickers: the
 *  currency switch on Account Balance and "This Year" on Overview. */
export interface SelectProps {
  value?: string;
  options?: string[];
  onChange?: (value: string) => void;
  /** Optional leading element, e.g. a flag image. */
  leading?: React.ReactNode;
  variant?: 'ghost' | 'outline' | 'sunken';
  size?: 'sm' | 'md';
  style?: React.CSSProperties;
}
export declare function Select(props: SelectProps): JSX.Element;
