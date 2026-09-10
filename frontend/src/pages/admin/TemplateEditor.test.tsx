import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as adminApi from '../../api/admin';
import type { AllocationTemplateResponse, AssetClassResponse } from '../../api/admin';
import { TemplateEditor } from './TemplateEditor';

const ASSET_CLASSES: AssetClassResponse[] = [
  { id: 1, code: 'EQ_DM', name: 'Developed-Market Equity' },
  { id: 2, code: 'EQ_EM', name: 'Emerging-Market Equity' },
  { id: 3, code: 'FI_GOV', name: 'Government Fixed Income' },
];

const MODERATE_HISTORY: AllocationTemplateResponse[] = [
  {
    id: 8,
    version: 3,
    risk_band: 'MODERATE',
    allocations: [
      { asset_class_id: 1, asset_class_code: 'EQ_DM', percent: '40.00' },
      { asset_class_id: 2, asset_class_code: 'EQ_EM', percent: '35.00' },
      { asset_class_id: 3, asset_class_code: 'FI_GOV', percent: '25.00' },
    ],
    total_percent: '100.00',
    published_at: '2026-08-14T09:00:00Z',
    is_active: true,
  },
];

async function renderReady() {
  const user = userEvent.setup();
  render(<TemplateEditor />);
  await screen.findByTestId('allocation-percent-0');
  return user;
}

describe('TemplateEditor', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'getAssetClasses').mockResolvedValue(ASSET_CLASSES);
    vi.spyOn(adminApi, 'getAllocationTemplates').mockResolvedValue(MODERATE_HISTORY);
  });

  it('shows a running total of 90.00 with a warning/error treatment when percentages do not sum to 100', async () => {
    const user = await renderReady();

    await user.clear(screen.getByTestId('allocation-percent-0'));
    await user.type(screen.getByTestId('allocation-percent-0'), '60.00');
    await user.clear(screen.getByTestId('allocation-percent-1'));
    await user.type(screen.getByTestId('allocation-percent-1'), '30.00');

    const total = await screen.findByTestId('allocation-total');
    expect(total).toHaveTextContent('90.00');
    expect(total.className).toContain('invalid');
  });

  it('keeps Publish disabled while the running total is not exactly 100.00', async () => {
    const user = await renderReady();

    await user.clear(screen.getByTestId('allocation-percent-0'));
    await user.type(screen.getByTestId('allocation-percent-0'), '60.00');
    await user.clear(screen.getByTestId('allocation-percent-1'));
    await user.type(screen.getByTestId('allocation-percent-1'), '30.00');

    expect(screen.getByTestId('publish')).toBeDisabled();
  });

  it('enables Publish once entered percentages sum to exactly 100.00', async () => {
    const user = await renderReady();

    await user.clear(screen.getByTestId('allocation-percent-0'));
    await user.type(screen.getByTestId('allocation-percent-0'), '60.00');
    await user.clear(screen.getByTestId('allocation-percent-1'));
    await user.type(screen.getByTestId('allocation-percent-1'), '40.00');

    const total = await screen.findByTestId('allocation-total');
    expect(total).toHaveTextContent('100.00');
    expect(total.className).toContain('valid');
    expect(screen.getByTestId('publish')).toBeEnabled();
  });

  it('publishing a new version refreshes the version-history list via state update, without navigation', async () => {
    const updatedHistory: AllocationTemplateResponse[] = [
      ...MODERATE_HISTORY,
      {
        id: 11,
        version: 4,
        risk_band: 'MODERATE',
        allocations: [{ asset_class_id: 1, asset_class_code: 'EQ_DM', percent: '100.00' }],
        total_percent: '100.00',
        published_at: '2026-09-05T10:00:00Z',
        is_active: true,
      },
    ];
    (adminApi.getAllocationTemplates as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(MODERATE_HISTORY)
      .mockResolvedValueOnce(updatedHistory);
    const publishSpy = vi.spyOn(adminApi, 'publishAllocationTemplate').mockResolvedValue({
      id: 11,
      version: 4,
      risk_band: 'MODERATE',
      total_percent: '100.00',
      published_at: '2026-09-05T10:00:00Z',
      is_active: true,
    });
    const user = await renderReady();

    await user.clear(screen.getByTestId('allocation-percent-0'));
    await user.type(screen.getByTestId('allocation-percent-0'), '100.00');
    await waitFor(() => expect(screen.getByTestId('publish')).toBeEnabled());
    await user.click(screen.getByTestId('publish'));

    await waitFor(() => expect(publishSpy).toHaveBeenCalledWith({
      risk_band: 'MODERATE',
      allocations: [
        { asset_class_id: 1, percent: '100.00' },
        { asset_class_id: 2, percent: '0.00' },
        { asset_class_id: 3, percent: '0.00' },
      ],
    }));
    expect(await screen.findByText('4')).toBeInTheDocument();
  });

  it('lists the asset classes as editable rows sourced from GET /api/admin/asset-classes', async () => {
    await renderReady();

    expect(screen.getByText('Developed-Market Equity')).toBeInTheDocument();
    expect(screen.getByText('Emerging-Market Equity')).toBeInTheDocument();
    expect(screen.getByText('Government Fixed Income')).toBeInTheDocument();
  });

  it('supports removing an allocation row, excluding it from the running total', async () => {
    const user = await renderReady();

    await user.click(screen.getByRole('button', { name: /remove row 1/i }));

    expect(screen.queryByText('Developed-Market Equity')).not.toBeInTheDocument();
    const total = await screen.findByTestId('allocation-total');
    expect(total).toHaveTextContent('0.00');
  });
});
