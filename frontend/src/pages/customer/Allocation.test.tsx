import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as recommendationApi from '../../api/recommendation';
import type { RecommendationResponse } from '../../api/recommendation';
import { Allocation } from './Allocation';

const MODERATE_RECOMMENDATION: RecommendationResponse = {
  risk_band: 'MODERATE',
  rule_version: 1,
  template_version: 2,
  horizon: 'LONG',
  allocations: [
    {
      asset_class_id: 1,
      asset_class_code: 'EQ_DM',
      asset_class_name: 'Developed-Market Equity',
      percent: '40.00',
    },
    {
      asset_class_id: 2,
      asset_class_code: 'FI_GOV',
      asset_class_name: 'Government Fixed Income',
      percent: '35.00',
    },
    { asset_class_id: 3, asset_class_code: 'CASH', asset_class_name: 'Cash', percent: '25.00' },
  ],
  total_percent: '100.00',
  generated_at: '2026-09-03T10:20:00Z',
};

const THIRDS_RECOMMENDATION: RecommendationResponse = {
  risk_band: 'AGGRESSIVE',
  rule_version: 1,
  template_version: 3,
  horizon: 'LONG',
  allocations: [
    {
      asset_class_id: 1,
      asset_class_code: 'EQ_DM',
      asset_class_name: 'Developed-Market Equity',
      percent: '33.34',
    },
    {
      asset_class_id: 2,
      asset_class_code: 'FI_GOV',
      asset_class_name: 'Government Fixed Income',
      percent: '33.33',
    },
    { asset_class_id: 3, asset_class_code: 'CASH', asset_class_name: 'Cash', percent: '33.33' },
  ],
  total_percent: '100.00',
  generated_at: '2026-09-03T10:20:00Z',
};

const CONSERVATIVE_RECOMMENDATION: RecommendationResponse = {
  risk_band: 'CONSERVATIVE',
  rule_version: 1,
  template_version: 1,
  horizon: 'SHORT',
  allocations: [
    { asset_class_id: 3, asset_class_code: 'CASH', asset_class_name: 'Cash', percent: '100.00' },
  ],
  total_percent: '100.00',
  generated_at: '2026-09-04T09:00:00Z',
};

function renderAllocation() {
  return render(
    <MemoryRouter>
      <Allocation />
    </MemoryRouter>
  );
}

describe('Allocation', () => {
  it('renders one row per allocation with a client-computed total of 100.00', async () => {
    vi.spyOn(recommendationApi, 'getRecommendation').mockResolvedValue(MODERATE_RECOMMENDATION);
    renderAllocation();

    expect(await screen.findByText('EQ_DM')).toBeInTheDocument();
    expect(screen.getByText('FI_GOV')).toBeInTheDocument();
    expect(screen.getByText('CASH')).toBeInTheDocument();
    expect(screen.getByTestId('allocation-total')).toHaveTextContent('100.00');
  });

  it('shows a questionnaire prompt instead of an empty table on 404 NO_RISK_BAND_ASSIGNMENT', async () => {
    vi.spyOn(recommendationApi, 'getRecommendation').mockRejectedValue(
      new ApiError(404, 'NO_RISK_BAND_ASSIGNMENT', 'No risk band assigned.')
    );
    renderAllocation();

    const prompt = await screen.findByTestId('no-risk-band-prompt');
    expect(prompt).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    const link = screen.getByRole('link', { name: /risk-profile questionnaire/i });
    expect(link).toHaveAttribute('href', '/customer/questionnaire');
  });

  it('renders every percentage with exactly two decimal places and no floating-point artifact', async () => {
    vi.spyOn(recommendationApi, 'getRecommendation').mockResolvedValue(THIRDS_RECOMMENDATION);
    renderAllocation();

    await screen.findByText('EQ_DM');
    expect(screen.getByText('33.34')).toBeInTheDocument();
    expect(screen.getAllByText('33.33')).toHaveLength(2);
    expect(screen.getByTestId('allocation-total')).toHaveTextContent('100.00');
    expect(screen.queryByText(/33\.330000000000005/)).not.toBeInTheDocument();
  });

  it('refetches and re-renders the allocations on window focus, without unmounting the page', async () => {
    const getRecommendationSpy = vi
      .spyOn(recommendationApi, 'getRecommendation')
      .mockResolvedValueOnce(MODERATE_RECOMMENDATION)
      .mockResolvedValueOnce(CONSERVATIVE_RECOMMENDATION);
    renderAllocation();

    await screen.findByText('EQ_DM');
    expect(getRecommendationSpy).toHaveBeenCalledTimes(1);
    const headingBefore = screen.getByRole('heading', { name: 'Recommended allocation' });

    window.dispatchEvent(new Event('focus'));

    await waitFor(() => expect(getRecommendationSpy).toHaveBeenCalledTimes(2));
    await screen.findByText('CASH');
    expect(screen.queryByText('EQ_DM')).not.toBeInTheDocument();
    expect(screen.getByTestId('allocation-total')).toHaveTextContent('100.00');

    const headingAfter = screen.getByRole('heading', { name: 'Recommended allocation' });
    expect(headingAfter).toBe(headingBefore);
  });
});
