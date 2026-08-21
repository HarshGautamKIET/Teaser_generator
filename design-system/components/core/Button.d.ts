import * as React from 'react';

/**
 * Pill-shaped action button. Primary green for the single most important
 * action in a card, grey secondary beside it, near-black for utility
 * actions in the page header (Export).
 *
 * @startingPoint section="Core" subtitle="Pill buttons, five fills" viewport="700x150"
 */
export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'dark' | 'outline' | 'ghost' | 'onBrand';
  size?: 'sm' | 'md' | 'lg';
  /** Leading glyph — pass a Lucide <i data-lucide> span or an <svg>. */
  icon?: React.ReactNode;
  iconRight?: React.ReactNode;
  fullWidth?: boolean;
  disabled?: boolean;
  as?: 'button' | 'a';
  children?: React.ReactNode;
  style?: React.CSSProperties;
  onClick?: (e: React.MouseEvent) => void;
}
export declare function Button(props: ButtonProps): JSX.Element;
