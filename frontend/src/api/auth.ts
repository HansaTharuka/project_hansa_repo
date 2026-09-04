/**
 * `/api/auth/*` calls (E2-S3 AC1, AC4, AC5; api-contracts.md §5.1, §5.2).
 */
import type { Role } from '../types/entities';
import { apiRequest, setStoredToken } from './client';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
  expires_in: number;
}

export interface CurrentUserResponse {
  user_id: number;
  email: string;
  role: Role;
  customer_id: number | null;
}

/** POST /api/auth/login — on success, persists the token so every later
 * request through `api/client.ts` carries it automatically (AC4). */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const result = await apiRequest<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: { email, password },
  });
  setStoredToken(result.access_token);
  return result;
}

/** GET /api/auth/me — the session-restore read (AC5): a server-verified
 * identity check, not a client-side `exp` decode. */
export function getCurrentUser(): Promise<CurrentUserResponse> {
  return apiRequest<CurrentUserResponse>('/api/auth/me');
}

export function logout(): void {
  setStoredToken(null);
}
