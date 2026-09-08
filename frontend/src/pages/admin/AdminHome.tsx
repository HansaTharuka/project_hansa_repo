/**
 * Admin console nav hub (E10-S4) — links to the three scored admin screens
 * (allocation template editor, risk-band rule editor, asset-class master)
 * plus the rebalancing-threshold publisher. `router.tsx` mounts this at
 * `/admin`; the individual screens each live at their own `/admin/*` route
 * (see this story's final report for the exact paths the integrator wires).
 */
import { Link } from 'react-router-dom';

export function AdminHome() {
  return (
    <main className="admin-page">
      <h2>Admin console</h2>
      <p className="sub">
        Rules and templates are insert-only and immutable once published (AC-10). Publishing
        creates a new version; customers already assigned stay pinned to the version active at
        assignment time.
      </p>
      <section className="panel">
        <ul className="quick-links">
          <li>
            <Link to="/admin/templates">Allocation template editor</Link>
          </li>
          <li>
            <Link to="/admin/rules">Risk-band rule editor</Link>
          </li>
          <li>
            <Link to="/admin/asset-classes">Asset-class master</Link>
          </li>
          <li>
            <Link to="/admin/threshold">Rebalancing threshold</Link>
          </li>
        </ul>
      </section>
    </main>
  );
}
