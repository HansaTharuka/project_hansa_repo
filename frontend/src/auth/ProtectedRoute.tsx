/**
 * Role-gated route guard (E2-S3 AC1). Redirects an unauthenticated caller to
 * `/login`, and an authenticated caller whose role is not in `allowedRoles`
 * to their own landing route (never a silent blank page).
 */
import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import type { Role } from '../types/entities';
import { useAuth } from './AuthContext';
import { roleRedirect } from './roleRedirect';

interface ProtectedRouteProps {
  allowedRoles: Role[];
  children: ReactNode;
}

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <p>Loading…</p>;
  }
  if (user === null) {
    return <Navigate to="/login" replace />;
  }
  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={roleRedirect(user.role)} replace />;
  }
  return <>{children}</>;
}
