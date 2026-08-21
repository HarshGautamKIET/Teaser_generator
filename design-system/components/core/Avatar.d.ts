import * as React from 'react';

/** Circular user image with initials fallback. Sits at the far right of
 *  the top bar beside a small up/down switcher chevron. */
export interface AvatarProps {
  src?: string;
  /** Used for alt text and the initials fallback. */
  name?: string;
  size?: number;
  ring?: boolean;
  style?: React.CSSProperties;
}
export declare function Avatar(props: AvatarProps): JSX.Element;
