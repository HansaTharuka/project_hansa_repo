import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import * as advisorApi from '../../api/advisor';
import type { AdvisorOverrideResponse } from '../../api/advisor';
import { OverrideForm } from './OverrideForm';

const OVERRIDE_RESULT: AdvisorOverrideResponse = {
  override_id: 4,
  customer_id: 3,
  previous_band: 'MODERATE',
  new_band: 'CONSERVATIVE',
  reason: 'Client reported imminent liquidity need',
  note: null,
  created_at: '2026-09-04T14:05:00Z',
  assignment_id: 13,
  risk_band: 'CONSERVATIVE',
};

describe('OverrideForm', () => {
  it('shows an inline validation error and does not call the override API when reason is left blank', async () => {
    const user = userEvent.setup();
    const overrideSpy = vi.spyOn(advisorApi, 'overrideRiskBand');
    const onOverridden = vi.fn();
    render(<OverrideForm customerId={3} currentBand="MODERATE" onOverridden={onOverridden} />);

    await user.selectOptions(screen.getByLabelText(/new_band/), 'CONSERVATIVE');
    await user.click(screen.getByTestId('override-submit'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/reason is required/i);
    expect(overrideSpy).not.toHaveBeenCalled();
    expect(onOverridden).not.toHaveBeenCalled();
  });

  it('submits the override with the entered fields and calls onOverridden on success', async () => {
    const user = userEvent.setup();
    vi.spyOn(advisorApi, 'overrideRiskBand').mockResolvedValue(OVERRIDE_RESULT);
    const onOverridden = vi.fn();
    render(<OverrideForm customerId={3} currentBand="MODERATE" onOverridden={onOverridden} />);

    await user.selectOptions(screen.getByLabelText(/new_band/), 'CONSERVATIVE');
    await user.type(screen.getByLabelText(/reason/), 'Client reported imminent liquidity need');
    await user.click(screen.getByTestId('override-submit'));

    expect(advisorApi.overrideRiskBand).toHaveBeenCalledWith(3, {
      new_band: 'CONSERVATIVE',
      reason: 'Client reported imminent liquidity need',
      note: undefined,
    });
    await waitFor(() => expect(onOverridden).toHaveBeenCalledTimes(1));
  });

  it('shows the API error message and does not call onOverridden when the override request fails', async () => {
    const user = userEvent.setup();
    const { ApiError } = await import('../../api/client');
    vi.spyOn(advisorApi, 'overrideRiskBand').mockRejectedValue(
      new ApiError(409, 'NO_PRIOR_ASSIGNMENT', 'The customer has no prior risk band assignment.')
    );
    const onOverridden = vi.fn();
    render(<OverrideForm customerId={3} currentBand={null} onOverridden={onOverridden} />);

    await user.type(screen.getByLabelText(/reason/), 'Client reported imminent liquidity need');
    await user.click(screen.getByTestId('override-submit'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/no prior risk band assignment/i);
    expect(onOverridden).not.toHaveBeenCalled();
  });
});
