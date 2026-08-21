import * as React from 'react';

/** Thin wrapper around the Lucide CDN sprite — the brand's icon set.
 *  Intentional addition (see readme.md → Intentional additions): the
 *  reference render is a raster, so glyphs are re-sourced from Lucide. */
export interface IconProps {
  /** Lucide icon name, kebab-case, e.g. "wallet", "more-horizontal". */
  name: string;
  size?: number;
  /** 2 for UI chrome, 2.2 for the 14px glyphs inside icon tiles. */
  strokeWidth?: number;
  color?: string;
  style?: React.CSSProperties;
}
export declare function Icon(props: IconProps): JSX.Element;
