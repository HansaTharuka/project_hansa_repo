import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiRequest, getStoredToken, setStoredToken } from './client';

describe('apiRequest', () => {
  beforeEach(() => {
    setStoredToken(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('attaches Authorization: Bearer <token> when a token is stored', async () => {
    setStoredToken('stored-token-abc');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await apiRequest('/api/holdings');

    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer stored-token-abc');
  });

  it('sends no Authorization header when no token is stored', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await apiRequest('/api/health');

    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Record<string, string>;
    expect(headers['Authorization']).toBeUndefined();
  });

  it('throws ApiError with the decoded code and message on a non-2xx response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect email or password.' } }),
        { status: 401 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiRequest('/api/auth/login', { method: 'POST', body: {} })).rejects.toMatchObject(
      { code: 'INVALID_CREDENTIALS', status: 401 },
    );
  });

  it('rejects with an instance of ApiError specifically', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: 'nope' } }), {
          status: 404,
        }),
      ),
    );

    await expect(apiRequest('/api/x')).rejects.toBeInstanceOf(ApiError);
  });

  it('setStoredToken persists and getStoredToken reads it back', () => {
    setStoredToken('round-trip-token');
    expect(getStoredToken()).toBe('round-trip-token');
    expect(window.localStorage.getItem('wealthwise.access_token')).toBe('round-trip-token');
  });

  it('setStoredToken(null) clears storage', () => {
    setStoredToken('to-be-cleared');
    setStoredToken(null);
    expect(getStoredToken()).toBeNull();
    expect(window.localStorage.getItem('wealthwise.access_token')).toBeNull();
  });
});
