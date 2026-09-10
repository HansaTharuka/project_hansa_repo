/**
 * The single fetch wrapper every API module goes through (E2-S3 AC4).
 *
 * Owns the access-token store (`localStorage`) and attaches
 * `Authorization: Bearer <token>` to every request when a token is present —
 * no other module reads or writes `localStorage` directly. Always reads
 * through to storage (no in-memory cache) so this module's state can never
 * drift from what a page refresh would actually see.
 */

const TOKEN_STORAGE_KEY = 'wealthwise.access_token';

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token === null) {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } else {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string };
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

interface ApiRequestOptions {
  method?: HttpMethod;
  body?: unknown;
}

function baseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
}

/** Perform one JSON request against the backend, attaching the stored bearer
 * token when present. Throws `ApiError` (never a raw `Response`) on any
 * non-2xx status, decoding the `{ "error": { "code", "message" } }` envelope
 * every backend error response uses. */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getStoredToken();
  if (token !== null) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${baseUrl()}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    throw await buildApiError(response);
  }
  return (await response.json()) as T;
}

async function buildApiError(response: Response): Promise<ApiError> {
  const parsed: ErrorEnvelope | null = await response.json().catch(() => null);
  const code = parsed?.error.code ?? 'UNKNOWN_ERROR';
  const message = parsed?.error.message ?? `Request failed with status ${response.status}`;
  return new ApiError(response.status, code, message);
}
