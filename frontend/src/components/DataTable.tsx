/**
 * Generic, reusable, read-only data table (E3-S4 — supports the compliance
 * audit-log screen; no edit/delete/update control is rendered anywhere in
 * this component, by construction — it never accepts an "actions" column).
 */
import type { ReactNode } from 'react';

export interface DataTableColumn<T> {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  numeric?: boolean;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string | number;
  rowProps?: (row: T) => Record<string, string>;
  emptyMessage?: string;
  caption?: string;
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  rowProps,
  emptyMessage = 'No results.',
  caption,
}: DataTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="empty" data-testid="empty-state">
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="tablewrap">
      <table>
        {caption !== undefined && <caption className="sub">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.numeric ? 'num' : undefined}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)} {...(rowProps ? rowProps(row) : {})}>
              {columns.map((column) => (
                <td key={column.key} className={column.numeric ? 'num' : undefined}>
                  {column.render
                    ? column.render(row)
                    : String((row as Record<string, unknown>)[column.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
