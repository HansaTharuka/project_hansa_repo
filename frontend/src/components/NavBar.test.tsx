import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as authApi from '../api/auth';
import { AuthProvider } from '../auth/AuthContext';
import { NavBar } from './NavBar';

function renderNavBar() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <NavBar />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('NavBar', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders no account nav when there is no signed-in user', () => {
    vi.spyOn(authApi, 'getCurrentUser').mockRejectedValue(new Error('no session'));
    renderNavBar();

    expect(screen.queryByRole('navigation', { name: 'Account' })).not.toBeInTheDocument();
  });

  it('renders a persistent Holdings link for a customer-role user', async () => {
    window.localStorage.setItem('wealthwise.access_token', 'tok-1');
    vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({
      user_id: 3,
      email: 'customer03@wealthwise.test',
      role: 'customer',
      customer_id: 3,
    });
    renderNavBar();

    const link = await screen.findByRole('link', { name: 'Holdings' });
    expect(link).toHaveAttribute('href', '/customer/holdings');
  });

  it('renders no Holdings link for a non-customer-role user', async () => {
    window.localStorage.setItem('wealthwise.access_token', 'tok-1');
    vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({
      user_id: 11,
      email: 'advisor01@wealthwise.test',
      role: 'advisor',
      customer_id: null,
    });
    renderNavBar();

    await screen.findByText(/advisor01@wealthwise\.test/);
    expect(screen.queryByRole('link', { name: 'Holdings' })).not.toBeInTheDocument();
  });
});
