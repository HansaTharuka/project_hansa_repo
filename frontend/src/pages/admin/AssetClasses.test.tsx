import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as adminApi from '../../api/admin';
import type { AssetClassResponse } from '../../api/admin';
import { AssetClasses } from './AssetClasses';

const ASSET_CLASSES: AssetClassResponse[] = [
  { id: 1, code: 'EQ_DM', name: 'Developed-Market Equity' },
  { id: 2, code: 'FI_GOV', name: 'Government Fixed Income' },
];

async function renderReady() {
  const user = userEvent.setup();
  render(<AssetClasses />);
  await screen.findByText('EQ_DM');
  return user;
}

describe('AssetClasses', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'getAssetClasses').mockResolvedValue(ASSET_CLASSES);
  });

  it('lists every asset class from GET /api/admin/asset-classes', async () => {
    await renderReady();

    expect(screen.getByText('EQ_DM')).toBeInTheDocument();
    expect(screen.getByText('Government Fixed Income')).toBeInTheDocument();
  });

  it('adding a new asset class calls the create API and appends it to the list', async () => {
    const createSpy = vi.spyOn(adminApi, 'createAssetClass').mockResolvedValue({
      id: 3,
      code: 'REIT',
      name: 'Listed Real Estate',
    });
    const user = await renderReady();

    await user.type(screen.getByLabelText(/code/i), 'REIT');
    await user.type(screen.getByLabelText(/name/i), 'Listed Real Estate');
    await user.click(screen.getByRole('button', { name: /add asset class/i }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledWith({ code: 'REIT', name: 'Listed Real Estate' }));
    expect(await screen.findByText('REIT')).toBeInTheDocument();
  });

  it('submitting a duplicate code shows an inline error sourced from the 409 response body', async () => {
    vi.spyOn(adminApi, 'createAssetClass').mockRejectedValue(
      new ApiError(409, 'DUPLICATE_ASSET_CLASS_CODE', "AssetClass code 'EQ_DM' is already in use."),
    );
    const user = await renderReady();

    await user.type(screen.getByLabelText(/code/i), 'EQ_DM');
    await user.type(screen.getByLabelText(/name/i), 'Duplicate of an existing code');
    await user.click(screen.getByRole('button', { name: /add asset class/i }));

    expect(await screen.findByText("AssetClass code 'EQ_DM' is already in use.")).toBeInTheDocument();
    expect(screen.getByLabelText(/code/i)).toHaveAttribute('aria-invalid', 'true');
  });

  it('a generic (non-409) failure shows a fallback error, not a silent failure', async () => {
    vi.spyOn(adminApi, 'createAssetClass').mockRejectedValue(new Error('network down'));
    const user = await renderReady();

    await user.type(screen.getByLabelText(/code/i), 'COMMODITY');
    await user.type(screen.getByLabelText(/name/i), 'Broad commodities');
    await user.click(screen.getByRole('button', { name: /add asset class/i }));

    expect(await screen.findByText(/could not be added/i)).toBeInTheDocument();
  });
});
