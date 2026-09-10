/**
 * The persona-to-landing-screen mapping (E2-S3 AC1). Every route path here
 * is a stub in `router.tsx` until the owning epic's UI story replaces it.
 */
import type { Role } from '../types/entities';

const ROLE_LANDING_ROUTES: Record<Role, string> = {
  customer: '/customer/dashboard',
  advisor: '/advisor/customers',
  admin: '/admin',
  compliance: '/compliance/audit-log',
};

export function roleRedirect(role: Role): string {
  return ROLE_LANDING_ROUTES[role];
}
