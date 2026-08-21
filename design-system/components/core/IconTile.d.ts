import * as React from 'react';

/** Small rounded-square glyph holder that precedes every card title and
 *  savings-goal row. 28px, radius 8, pale tint of the tone colour. */
export interface IconTileProps {
  children?: React.ReactNode;
  tone?: 'brand' | 'neutral' | 'amber' | 'white';
  size?: number;
  style?: React.CSSProperties;
}
export declare function IconTile(props: IconTileProps): JSX.Element;
