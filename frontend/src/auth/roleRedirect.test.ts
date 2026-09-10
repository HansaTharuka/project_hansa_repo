import { describe, expect, it } from 'vitest';

import { roleRedirect } from './roleRedirect';

describe('roleRedirect', () => {
  it.each([
    ['customer', '/customer/dashboard'],
    ['advisor', '/advisor/customers'],
    ['admin', '/admin'],
    ['compliance', '/compliance/audit-log'],
  ] as const)('maps %s to %s', (role, expectedPath) => {
    expect(roleRedirect(role)).toBe(expectedPath);
  });
});
