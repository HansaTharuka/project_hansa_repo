/**
 * The authenticated-session chrome (E2-S3). Extended with persona-specific
 * links by every later UI story (component-map.md) — E6-S5 adds the
 * customer's persistent "Holdings" link (AC5), rendered on every
 * customer-role page since `NavBar` lives inside `Layout`, wrapping every
 * protected route.
 */
import { Link } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

export function NavBar() {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <h1>WealthWise</h1>
      {user !== null && (
        <nav aria-label="Primary">
          {user.role === 'customer' && (
            <>
              <Link to="/customer/holdings">Holdings</Link>
              <Link to="/customer/goals">Goals</Link>
              <Link to="/customer/rebalancing">Rebalancing</Link>
            </>
          )}
        </nav>
      )}
      {user !== null && (
        <nav aria-label="Account">
          <span>
            {user.email} ({user.role})
          </span>
          <button type="button" onClick={logout}>
            Sign out
          </button>
        </nav>
      )}
    </header>
  );
}
