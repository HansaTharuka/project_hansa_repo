import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as authApi from '../api/auth';
import { setStoredToken } from '../api/client';
import { AuthProvider, useAuth } from './AuthContext';

function Probe() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <p>loading</p>;
  return <p>{user === null ? 'anonymous' : `${user.email}:${user.role}`}</p>;
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('after a successful login, persists the token and attaches it to the next request', async () => {
    vi.spyOn(authApi, 'login').mockImplementation(async () => {
      setStoredToken('mock-token-123');
      return {
        access_token: 'mock-token-123',
        token_type: 'bearer',
        role: 'customer',
        expires_in: 3600,
      };
    });
    vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({
      user_id: 3,
      email: 'customer03@wealthwise.test',
      role: 'customer',
      customer_id: 3,
    });

    let capturedLogin: ((email: string, password: string) => Promise<string>) | null = null;
    function Capture() {
      const { login } = useAuth();
      capturedLogin = login;
      return null;
    }

    render(
      <AuthProvider>
        <Capture />
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument());

    await act(async () => {
      await capturedLogin?.('customer03@wealthwise.test', 'DemoPass!2026');
    });

    expect(window.localStorage.getItem('wealthwise.access_token')).toBe('mock-token-123');
    await waitFor(() =>
      expect(screen.getByText('customer03@wealthwise.test:customer')).toBeInTheDocument(),
    );
  });

  it('restores an existing session from storage without redirecting to login', async () => {
    setStoredToken('already-stored-token');
    vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({
      user_id: 11,
      email: 'advisor01@wealthwise.test',
      role: 'advisor',
      customer_id: null,
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(screen.getByText('loading')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText('advisor01@wealthwise.test:advisor')).toBeInTheDocument(),
    );
    expect(authApi.getCurrentUser).toHaveBeenCalledTimes(1);
  });

  it('with no stored token, resolves to an anonymous session without calling GET /api/auth/me', async () => {
    const spy = vi.spyOn(authApi, 'getCurrentUser');

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument());
    expect(spy).not.toHaveBeenCalled();
  });
});
