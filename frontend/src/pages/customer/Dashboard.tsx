/**
 * Customer landing/nav hub (E4-S4; roleRedirect.ts routes `customer` here on
 * login). Kept intentionally simple — a set of quick links into the screens
 * that exist as of this story; later UI stories may extend this list without
 * changing its shape.
 */
import { Link } from 'react-router-dom';

export function Dashboard() {
  return (
    <main className="dashboard-page">
      <h2>Dashboard</h2>
      <p className="sub">Welcome back. Pick up where you left off.</p>
      <section className="panel">
        <ul className="quick-links">
          <li>
            <Link to="/customer/questionnaire">Risk-profile questionnaire</Link>
          </li>
          <li>
            <Link to="/customer/holdings">Holdings &amp; drift</Link>
          </li>
        </ul>
      </section>
    </main>
  );
}
