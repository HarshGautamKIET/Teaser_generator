import * as React from 'react';

/** The app's left rail: uppercase section labels ("MAIN MENU", "FEATURES",
 *  "GENERAL") over 38px nav rows. The active row gets a pale green pill, a
 *  green 3px left tick and green label; counts sit flush right in grey.
 *
 * @startingPoint section="Navigation" subtitle="Sidebar rail with grouped nav" viewport="700x380"
 */
export interface SidebarNavProps { children?: React.ReactNode; style?: React.CSSProperties }
export interface SidebarItemProps {
  icon?: React.ReactNode;
  label: string;
  /** Trailing count, e.g. 20 unread analytics reports. */
  count?: number | null;
  active?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export interface SidebarSectionLabelProps { children?: React.ReactNode; style?: React.CSSProperties }
export declare function SidebarNav(props: SidebarNavProps): JSX.Element;
export declare function SidebarItem(props: SidebarItemProps): JSX.Element;
export declare function SidebarSectionLabel(props: SidebarSectionLabelProps): JSX.Element;
