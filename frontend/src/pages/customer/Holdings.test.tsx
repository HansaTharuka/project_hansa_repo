import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import * as holdingsApi from '../../api/holdings';
import type { HoldingsResponse } from '../../api/holdings';
import { Holdings } from './Holdings';

const POPULATED_RESPONSE: HoldingsResponse = {
  as_of_date: '2026-09-04',
  total_value: '148387.40',
  threshold_bps: 500,
  threshold_percent: '5.00',
  holdings: [
    {
      asset_class_id: 1,
      asset_class_code: 'EQ_DM',
      current_value: '68420.50',
      current_percent: '46.11',
      target_percent: '40.00',
      drift_percent: '6.11',
      exceeds_threshold: true,
    },
    {
      asset_class_id: 6,
      asset_class_code: 'CASH',
      current_value: '5713.90',
      current_percent: '3.85',
      target_percent: '3.00',
      drift_percent: '0.85',
      exceeds_threshold: false,
    },
  ],
};

const EMPTY_RESPONSE: HoldingsResponse = {
  as_of_date: null,
  total_value: '0.00',
  threshold_bps: 500,
  threshold_percent: '5.00',
  holdings: [],
};

async function renderPopulated() {
  vi.spyOn(holdingsApi, 'getHoldings').mockResolvedValue(POPULATED_RESPONSE);
  render(<Holdings />);
  await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
  return within(screen.getByRole('table'));
}

describe('Holdings', () => {
  it('lists each held asset class with current_value, current_percent, target_percent, drift_percent', async () => {
    const table = await renderPopulated();

    const eqRow = table.getByText('EQ_DM').closest('tr');
    expect(eqRow).not.toBeNull();
    expect(within(eqRow as HTMLElement).getByText('68420.50')).toBeInTheDocument();
    expect(within(eqRow as HTMLElement).getByText('46.11')).toBeInTheDocument();
    expect(within(eqRow as HTMLElement).getByText('40.00')).toBeInTheDocument();
    expect(within(eqRow as HTMLElement).getByText('6.11')).toBeInTheDocument();
  });

  it('visually distinguishes a row whose drift exceeds the threshold via a data-breach attribute', async () => {
    const table = await renderPopulated();

    const breachedRow = table.getByText('EQ_DM').closest('tr');
    const okRow = table.getByText('CASH').closest('tr');
    expect(breachedRow).toHaveAttribute('data-breach', 'true');
    expect(okRow).toHaveAttribute('data-breach', 'false');
  });

  it('shows an explicit empty-state message for a customer with zero holdings', async () => {
    vi.spyOn(holdingsApi, 'getHoldings').mockResolvedValue(EMPTY_RESPONSE);
    render(<Holdings />);

    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('renders every money/percent value verbatim from the API string, never reformatted', async () => {
    const table = await renderPopulated();

    // "5713.90" would become "5713.9" under Number(x).toString() — verbatim
    // reproduction must keep the trailing zero (NFR-01).
    expect(table.getByText('5713.90')).toBeInTheDocument();
    expect(table.queryByText('5713.9')).not.toBeInTheDocument();
  });

  it('renders the portfolio summary total_value verbatim from the API', async () => {
    await renderPopulated();

    expect(screen.getAllByText('148387.40').length).toBeGreaterThan(0);
  });
});
