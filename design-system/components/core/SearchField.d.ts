import * as React from 'react';

/** Pill search input with a leading magnifier and a trailing ⌘K key cap.
 *  Sunken grey fill, no border. */
export interface SearchFieldProps {
  placeholder?: string;
  /** Key-cap label; pass null to hide. */
  shortcut?: string | null;
  width?: number | string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  style?: React.CSSProperties;
}
export declare function SearchField(props: SearchFieldProps): JSX.Element;
