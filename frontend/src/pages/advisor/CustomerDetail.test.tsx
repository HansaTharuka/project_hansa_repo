import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import * as advisorApi from '../../api/advisor';
import type {
  AdvisorCustomerDetailResponse,
  AdvisorOverrideResponse,
  ManualRecommendationResponse,
} from '../../api/advisor';
import { CustomerDetail } from './CustomerDetail';

const BASE_DETAIL: AdvisorCustomerDetailResponse = {
  customer_id: 3,
  email: 'customer03@wealthwise.test',
  kyc_verified: true,
  risk_band: 'MODERATE',
  rule_version: 1,
  holdings: {
    as_of_date: '2026-09-04',
    total_value: '100000.00',
    threshold_bps: 500,
    threshold_percent: '5.00',
    holdings: [
      {
        asset_class_id: 1,
        asset_class_code: 'EQ_DM',
        current_value: '40000.00',
        current_percent: '40.00',
        target_percent: '40.00',
        drift_percent: '0.00',
        exceeds_threshold: false,
      },
    ],
  },
  goals: [
    {
      id: 9,
      customer_id: 3,
      target_amount: '50000.00',
      target_date: '2032-01-01',
      priority: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      percent_complete: '10.00',
    },
  ],
  allocation: {
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
    ],
    total_percent: '100.00',
    generated_at: '2026-09-03T10:20:00Z',
  },
  override_history: [],
};

const OVERRIDDEN_DETAIL: AdvisorCustomerDetailResponse = {
  ...BASE_DETAIL,
  risk_band: 'CONSERVATIVE',
  override_history: [
    {
      id: 4,
      customer_id: 3,
      advisor_id: 11,
      previous_band: 'MODERATE',
      new_band: 'CONSERVATIVE',
      reason: 'Client reported imminent liquidity need',
      note: null,
      created_at: '2026-09-04T14:05:00Z',
    },
  ],
};

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

const MANUAL_REC_RESULT: ManualRecommendationResponse = {
  audit_entry_id: 512,
  customer_id: 3,
  advisor_id: 11,
  note: 'Recommended increasing cash weighting ahead of the client Q4 liquidity need.',
  created_at: '2026-09-04T14:10:00Z',
};

function LocationProbe({ onLocation }: { onLocation: (pathname: string) => void }) {
  const location = useLocation();
  useEffect(() => {
    onLocation(location.pathname);
  }, [location.pathname, onLocation]);
  return null;
}

function renderDetail(pathnames: string[]) {
  return render(
    <MemoryRouter initialEntries={['/advisor/customers/3']}>
      <LocationProbe onLocation={(pathname) => pathnames.push(pathname)} />
      <Routes>
        <Route path="/advisor/customers/:customerId" element={<CustomerDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('CustomerDetail', () => {
  it('renders holdings, goals and current allocation sections in the same tree', async () => {
    vi.spyOn(advisorApi, 'getAdvisorCustomerDetail').mockResolvedValue(BASE_DETAIL);
    renderDetail([]);

    expect(await screen.findByText('Holdings')).toBeInTheDocument();
    expect(screen.getByText('Goals')).toBeInTheDocument();
    expect(screen.getByText('Current allocation')).toBeInTheDocument();
    expect(screen.getAllByText(/EQ_DM/).length).toBeGreaterThan(0);
  });

  it('updates the displayed risk_band and override_history after a successful override, without navigating', async () => {
    const user = userEvent.setup();
    const pathnames: string[] = [];
    vi.spyOn(advisorApi, 'getAdvisorCustomerDetail')
      .mockResolvedValueOnce(BASE_DETAIL)
      .mockResolvedValueOnce(OVERRIDDEN_DETAIL);
    vi.spyOn(advisorApi, 'overrideRiskBand').mockResolvedValue(OVERRIDE_RESULT);
    renderDetail(pathnames);

    await screen.findByText(BASE_DETAIL.email);
    expect(screen.getByTestId('customer-risk-band')).toHaveTextContent('MODERATE');

    await user.selectOptions(screen.getByLabelText(/new_band/), 'CONSERVATIVE');
    await user.type(screen.getByLabelText(/reason/), 'Client reported imminent liquidity need');
    await user.click(screen.getByTestId('override-submit'));

    await waitFor(() =>
      expect(screen.getByTestId('customer-risk-band')).toHaveTextContent('CONSERVATIVE')
    );
    expect(screen.getByTestId('override-history')).toHaveTextContent(
      'Client reported imminent liquidity need'
    );
    expect(pathnames.every((pathname) => pathname === '/advisor/customers/3')).toBe(true);
  });

  it('opens the manual-recommendation modal without navigating and closes it on successful submit', async () => {
    const user = userEvent.setup();
    const pathnames: string[] = [];
    vi.spyOn(advisorApi, 'getAdvisorCustomerDetail').mockResolvedValue(BASE_DETAIL);
    vi.spyOn(advisorApi, 'postManualRecommendation').mockResolvedValue(MANUAL_REC_RESULT);
    renderDetail(pathnames);

    await screen.findByText(BASE_DETAIL.email);
    await user.click(screen.getByTestId('manual-rec-open'));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.type(screen.getByTestId('manual-rec-note'), MANUAL_REC_RESULT.note);
    await user.click(screen.getByTestId('manual-rec-submit'));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(pathnames.every((pathname) => pathname === '/advisor/customers/3')).toBe(true);
  });
});
