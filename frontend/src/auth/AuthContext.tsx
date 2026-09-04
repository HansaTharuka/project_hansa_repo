/**
 * The authenticated-session provider (E2-S3 AC4, AC5).
 *
 * On mount, if a token already exists in storage (a page refresh mid-session),
 * `GET /api/auth/me` restores the session server-side instead of redirecting
 * to `/login` — a client-side-only `exp` check is never trusted alone (AC5).
 */
import type { ReactNode } from 'react';
import { createContext, useContext, useEffect, useState } from 'react';

import type { CurrentUserResponse } from '../api/auth';
import { getCurrentUser, login as loginRequest, logout as clearStoredToken } from '../api/auth';
import { getStoredToken } from '../api/client';
import type { Role } from '../types/entities';

interface AuthContextValue {
  user: CurrentUserResponse | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<Role>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (token === null) {
      setIsLoading(false);
      return;
    }
    getCurrentUser()
      .then((details) => setUser(details))
      .catch(() => {
        clearStoredToken();
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<Role> {
    const result = await loginRequest(email, password);
    const details = await getCurrentUser();
    setUser(details);
    return result.role;
  }

  function logout(): void {
    clearStoredToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
