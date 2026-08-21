import * as React from 'react';

/** One currency balance in the "My Wallet" 2-up grid: flag + ISO code +
 *  vertical-dots menu, the balance, then Active / Inactive state text.
 *  Sits on --surface-tile, radius 12, no border. */
export interface WalletTileProps {
  /** Flag image element, e.g. <img src="assets/flag-usd.png" width={16} />. */
  flag?: React.ReactNode;
  code: string;
  amount: string;
  status?: 'active' | 'inactive';
  onMore?: () => void;
  style?: React.CSSProperties;
}
export declare function WalletTile(props: WalletTileProps): JSX.Element;
