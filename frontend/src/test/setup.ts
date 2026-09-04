/**
 * Vitest global setup — extends `expect` with jest-dom matchers (`toBeVisible`,
 * `toHaveAttribute`, ...) and clears `localStorage` between tests so no test's
 * persisted auth token leaks into the next (AuthContext.test.tsx).
 */
import '@testing-library/jest-dom/vitest';

import { afterEach } from 'vitest';

afterEach(() => {
  window.localStorage.clear();
});
