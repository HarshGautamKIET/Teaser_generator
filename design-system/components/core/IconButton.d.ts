import * as React from 'react';

/** Bare glyph affordance: header utilities (help, mail, bell) and the
 *  three-dot overflow on every card header. */
export interface IconButtonProps {
  children?: React.ReactNode;
  /** Required accessible name — these buttons carry no text. */
  label: string;
  variant?: 'outline' | 'ghost' | 'sunken';
  shape?: 'circle' | 'square';
  size?: number;
  style?: React.CSSProperties;
  onClick?: (e: React.MouseEvent) => void;
}
export declare function IconButton(props: IconButtonProps): JSX.Element;
