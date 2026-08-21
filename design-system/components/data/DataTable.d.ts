import * as React from 'react';

/** Recent-transaction list. Grey rounded header strip, hairline row rules,
 *  no outer border, no zebra striping. Cells accept nodes so an activity
 *  cell can hold an icon tile plus its label.
 *
 * @startingPoint section="Data" subtitle="Transaction table with status column" viewport="700x260"
 */
export interface DataTableColumn {
  key: string;
  label: string;
  /** Any grid track value, e.g. "1.6fr" or "90px". */
  width?: string;
  align?: 'left' | 'right' | 'center';
  /** Tabular figures for money and counts. */
  numeric?: boolean;
  /** Renders the cell in --text-body grey (dates). */
  muted?: boolean;
}
export interface DataTableProps {
  columns?: DataTableColumn[];
  rows?: Record<string, React.ReactNode>[];
  style?: React.CSSProperties;
}
export declare function DataTable(props: DataTableProps): JSX.Element;
