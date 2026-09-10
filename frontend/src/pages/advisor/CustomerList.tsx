/**
 * Advisor customer list (E9-S4 AC1; api-contracts.md §11.1). Every customer
 * with their current risk_band and a link into their drill-in view.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import type { AdvisorCustomerSummaryResponse } from '../../api/advisor';
import { getAdvisorCustomers } from '../../api/advisor';
import { EmptyState } from '../../components/EmptyState';
import { ErrorMessage } from '../../components/ErrorMessage';

export function CustomerList() {
  const [customers, setCustomers] = useState<AdvisorCustomerSummaryResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAdvisorCustomers()
      .then((result) => {
        if (!cancelled) {
          setCustomers(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Customers could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error !== null) {
    return (
      <main className="customer-list-page">
        <h2>Customers</h2>
        <ErrorMessage message={error} />
      </main>
    );
  }

  if (customers === null) {
    return (
      <main className="customer-list-page">
        <h2>Customers</h2>
        <p className="sub">Loading…</p>
      </main>
    );
  }

  return (
    <main className="customer-list-page">
      <h2>Customers</h2>
      <p className="sub">Every customer on this advisor&rsquo;s book, with their current risk band.</p>

      <section className="panel">
        {customers.length === 0 ? (
          <EmptyState
            message="No customers are assigned to you."
            hint="Customers appear here with their current risk_band once allocated to your book."
          />
        ) : (
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th scope="col" className="num">
                    customer_id
                  </th>
                  <th scope="col">email</th>
                  <th scope="col">risk_band</th>
                  <th scope="col">kyc_verified</th>
                  <th scope="col" className="num">
                    total_value
                  </th>
                  <th scope="col" className="num">
                    goal_count
                  </th>
                  <th scope="col"></th>
                </tr>
              </thead>
              <tbody>
                {customers.map((customer) => (
                  <tr key={customer.customer_id}>
                    <td className="num">{customer.customer_id}</td>
                    <td>
                      <code className="mono">{customer.email}</code>
                    </td>
                    <td>
                      <span className="band-pill">{customer.risk_band ?? 'null'}</span>
                    </td>
                    <td>{customer.kyc_verified ? 'true' : 'false'}</td>
                    <td className="num">{customer.total_value}</td>
                    <td className="num">{customer.goal_count}</td>
                    <td>
                      <Link
                        to={`/advisor/customers/${customer.customer_id}`}
                        data-testid="customer-drill-in-link"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
