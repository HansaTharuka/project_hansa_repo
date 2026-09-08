import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { RiskBandAssignmentResponse } from '../../api/riskProfile';
import { RiskResult } from './RiskResult';

const ASSIGNMENT_RESPONSE: RiskBandAssignmentResponse = {
  assignment_id: 13,
  customer_id: 3,
  risk_band: 'MODERATE',
  rule_version: 1,
  assigned_at: '2026-09-03T11:24:08Z',
};

function renderWithState(state: unknown) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/customer/risk-result', state }]}>
      <Routes>
        <Route path="/customer/risk-result" element={<RiskResult />} />
        <Route path="/customer/questionnaire" element={<p>Questionnaire landed</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RiskResult', () => {
  it('renders the returned risk_band in human-readable form (AC2)', () => {
    renderWithState(ASSIGNMENT_RESPONSE);

    expect(screen.getByText('Moderate')).toBeInTheDocument();
    expect(screen.getByText(/risk_band:\s*MODERATE/)).toBeInTheDocument();
  });

  it('renders assignment_id, rule_version and assigned_at from the response', () => {
    renderWithState(ASSIGNMENT_RESPONSE);

    expect(screen.getByText('13')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2026-09-03T11:24:08Z')).toBeInTheDocument();
  });

  it('falls back to a friendly message and a link back to the questionnaire when there is no navigation state', () => {
    renderWithState(undefined);

    expect(screen.queryByText('Moderate')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /take the risk-profile questionnaire/i })).toBeInTheDocument();
  });
});
