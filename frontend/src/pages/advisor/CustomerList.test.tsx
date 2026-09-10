import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import * as advisorApi from '../../api/advisor';
import type { AdvisorCustomerSummaryResponse } from '../../api/advisor';
import { CustomerList } from './CustomerList';

const CUSTOMERS: AdvisorCustomerSummaryResponse[] = [
  {
    customer_id: 3,
    email: 'customer03@wealthwise.test',
    risk_band: 'MODERATE',
    kyc_verified: true,
    total_value: '148387.40',
    goal_count: 3,
  },
  {
    customer_id: 10,
    email: 'customer10@wealthwise.test',
    risk_band: null,
    kyc_verified: true,
    total_value: '0.00',
    goal_count: 0,
  },
];

function renderList() {
  return render(
    <MemoryRouter>
      <CustomerList />
    </MemoryRouter>
  );
}

describe('CustomerList', () => {
  it('lists every customer with their risk_band and a link to its drill-in route', async () => {
    vi.spyOn(advisorApi, 'getAdvisorCustomers').mockResolvedValue(CUSTOMERS);
    renderList();

    expect(await screen.findByText('customer03@wealthwise.test')).toBeInTheDocument();
    expect(screen.getByText('MODERATE')).toBeInTheDocument();
    expect(screen.getByText('customer10@wealthwise.test')).toBeInTheDocument();
    expect(screen.getByText('null')).toBeInTheDocument();

    const links = screen.getAllByTestId('customer-drill-in-link');
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', '/advisor/customers/3');
    expect(links[1]).toHaveAttribute('href', '/advisor/customers/10');
  });

  it('shows an explicit empty-state when there are no customers', async () => {
    vi.spyOn(advisorApi, 'getAdvisorCustomers').mockResolvedValue([]);
    renderList();

    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
    expect(screen.queryByTestId('customer-drill-in-link')).not.toBeInTheDocument();
  });

  it('shows an error message when the customer list fails to load', async () => {
    vi.spyOn(advisorApi, 'getAdvisorCustomers').mockRejectedValue(new Error('network down'));
    renderList();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be loaded/i);
  });
});
