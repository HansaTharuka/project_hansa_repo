import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as adminApi from '../../api/admin';
import type { RebalancingThresholdResponse } from '../../api/admin';
import { ThresholdEditor } from './ThresholdEditor';

const CURRENT_THRESHOLD: RebalancingThresholdResponse[] = [
  {
    id: 1,
    version: 1,
    threshold_bps: 500,
    threshold_percent: '5.00',
    published_at: '2026-09-01T09:00:00Z',
    is_active: true,
  },
];

async function renderReady() {
  const user = userEvent.setup();
  render(<ThresholdEditor />);
  await screen.findByText('5.00');
  return user;
}

describe('ThresholdEditor', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'getRebalancingThresholds').mockResolvedValue(CURRENT_THRESHOLD);
  });

  it('lists the current threshold version history', async () => {
    await renderReady();

    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText('5.00')).toBeInTheDocument();
  });

  it('publishing a new threshold appends it to the history without navigation', async () => {
    const publishSpy = vi.spyOn(adminApi, 'publishRebalancingThreshold').mockResolvedValue({
      id: 2,
      version: 2,
      threshold_bps: 750,
      threshold_percent: '7.50',
      published_at: '2026-09-05T12:00:00Z',
      is_active: true,
    });
    const user = await renderReady();

    await user.clear(screen.getByLabelText(/threshold_bps/i));
    await user.type(screen.getByLabelText(/threshold_bps/i), '750');
    await user.click(screen.getByRole('button', { name: /publish/i }));

    await waitFor(() => expect(publishSpy).toHaveBeenCalledWith({ threshold_bps: 750 }));
    expect(await screen.findByText('7.50')).toBeInTheDocument();
  });

  it('rejects an out-of-range threshold_bps before calling the API', async () => {
    const publishSpy = vi.spyOn(adminApi, 'publishRebalancingThreshold');
    const user = await renderReady();

    await user.clear(screen.getByLabelText(/threshold_bps/i));
    await user.type(screen.getByLabelText(/threshold_bps/i), '15000');
    await user.click(screen.getByRole('button', { name: /publish/i }));

    expect(await screen.findByText(/between 1 and 10000/i)).toBeInTheDocument();
    expect(publishSpy).not.toHaveBeenCalled();
  });
});
