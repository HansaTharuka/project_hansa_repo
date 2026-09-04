import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as authApi from '../api/auth';
import { ApiError } from '../api/client';
import { AuthProvider } from '../auth/AuthContext';
import { Login } from './Login';

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/customer/dashboard" element={<p>Customer dashboard landed</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Login', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(authApi, 'getCurrentUser').mockRejectedValue(new Error('no session'));
  });

  it('the email and password inputs are labeled elements associated via for/id', () => {
    renderLogin();

    expect(screen.getByLabelText('Email')).toHaveAttribute('id', 'email');
    expect(screen.getByLabelText('Password')).toHaveAttribute('id', 'password');
  });

  it('submitting valid customer credentials navigates to the customer dashboard', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'tok-1',
      token_type: 'bearer',
      role: 'customer',
      expires_in: 3600,
    });
    vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({
      user_id: 3,
      email: 'customer03@wealthwise.test',
      role: 'customer',
      customer_id: 3,
    });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'customer03@wealthwise.test');
    await user.type(screen.getByLabelText('Password'), 'DemoPass!2026');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText('Customer dashboard landed')).toBeInTheDocument());
  });

  it('submitting invalid credentials shows an inline error and does not navigate', async () => {
    vi.spyOn(authApi, 'login').mockRejectedValue(
      new ApiError(401, 'INVALID_CREDENTIALS', 'Incorrect email or password.'),
    );
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'customer03@wealthwise.test');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('INVALID_CREDENTIALS');
    expect(screen.getByLabelText('Email')).toBeInTheDocument(); // still on the login screen
    expect(screen.queryByText('Customer dashboard landed')).not.toBeInTheDocument();
  });
});
