/**
 * The authenticated-session chrome (E2-S3). Extended with persona-specific
 * links by every later UI story (component-map.md) — this group only needs
 * the identity display and sign-out action, since Login is the only real
 * screen it ships.
 */
import { useAuth } from '../auth/AuthContext';

export function NavBar() {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <h1>WealthWise</h1>
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
