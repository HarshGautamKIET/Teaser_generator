import * as React from 'react';

/** Green upsell block pinned to the bottom of the sidebar. Vertical
 *  --green-600 → --green-800 gradient, centred copy, white pill button. */
export interface PromoCardProps {
  title?: React.ReactNode;
  body?: React.ReactNode;
  /** Usually <Button variant="onBrand" fullWidth>. */
  action?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function PromoCard(props: PromoCardProps): JSX.Element;
