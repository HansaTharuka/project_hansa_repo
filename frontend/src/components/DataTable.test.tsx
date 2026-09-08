import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DataTable } from './DataTable';

interface SampleRow {
  id: number;
  name: string;
  flagged: boolean;
}

const COLUMNS = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name' },
];

const ROWS: SampleRow[] = [
  { id: 1, name: 'Alpha', flagged: false },
  { id: 2, name: 'Beta', flagged: true },
];

describe('DataTable', () => {
  it('renders one column header per configured column', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(row) => row.id} />);

    expect(screen.getByRole('columnheader', { name: 'ID' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument();
  });

  it('renders one row per data item, in order', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(row) => row.id} />);

    const rows = screen.getAllByRole('row');
    // header row + 2 data rows
    expect(rows).toHaveLength(3);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('applies per-row data attributes supplied by rowProps, without adding any button', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(row) => row.id}
        rowProps={(row) => ({ 'data-breach': String(row.flagged) })}
      />,
    );

    const betaRow = screen.getByText('Beta').closest('tr');
    const alphaRow = screen.getByText('Alpha').closest('tr');
    expect(betaRow).toHaveAttribute('data-breach', 'true');
    expect(alphaRow).toHaveAttribute('data-breach', 'false');
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('renders a cell using a custom render function when supplied', () => {
    render(
      <DataTable
        columns={[
          { key: 'id', label: 'ID' },
          { key: 'flagged', label: 'Flagged', render: (row) => (row.flagged ? 'yes' : 'no') },
        ]}
        rows={ROWS}
        getRowKey={(row) => row.id}
      />,
    );

    expect(screen.getByText('yes')).toBeInTheDocument();
    expect(screen.getByText('no')).toBeInTheDocument();
  });

  it('renders an empty-state message instead of a table when rows is empty', () => {
    render(
      <DataTable<SampleRow>
        columns={COLUMNS}
        rows={[]}
        getRowKey={(row) => row.id}
        emptyMessage="No rows."
      />,
    );

    expect(screen.getByText('No rows.')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
