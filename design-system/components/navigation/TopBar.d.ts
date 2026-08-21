import * as React from 'react';

/** 56px application header: search on the left, utility icon buttons and the
 *  account avatar pushed right. BrandLockup is the mark + wordmark pair that
 *  sits at the top of the sidebar column. */
export interface TopBarProps {
  left?: React.ReactNode;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}
export interface BrandLockupProps {
  src?: string;
  name?: string;
  size?: number;
  style?: React.CSSProperties;
}
export declare function TopBar(props: TopBarProps): JSX.Element;
export declare function BrandLockup(props: BrandLockupProps): JSX.Element;
