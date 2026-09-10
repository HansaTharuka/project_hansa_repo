/**
 * Advisor drill-in view — holdings, goals, current allocation, override form
 * and manual-recommendation modal launcher, all on one screen (E9-S4
 * AC2-AC5; api-contracts.md §11.2).
 *
 * A successful override (AC4) or manual-recommendation log does not patch
 * local state ad hoc — it refetches the whole drill-in payload via
 * `getAdvisorCustomerDetail`, so the displayed risk_band and
 * `override_history` always reflect exactly what the server persisted, with
 * no navigation/full-page reload (single owner of this screen's read model).
 */
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import type { AdvisorCustomerDetailResponse } from '../../api/advisor';
import { getAdvisorCustomerDetail } from '../../api/advisor';
import { ErrorMessage } from '../../components/ErrorMessage';
import { formatBpsAsPercent, parsePercentToBps } from '../../lib/money';
import { ManualRecommendationModal } from './ManualRecommendationModal';
import { OverrideForm } from './OverrideForm';

function formatPercent(raw: string): string {
  const bps = parsePercentToBps(raw);
  return bps === null ? raw : formatBpsAsPercent(bps);
}

export function CustomerDetail() {
  const { customerId } = useParams<{ customerId: string }>();
  const parsedId = Number(customerId);

  const [detail, setDetail] = useState<AdvisorCustomerDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [manualRecOpen, setManualRecOpen] = useState(false);

  const loadDetail = useCallback((): void => {
    getAdvisorCustomerDetail(parsedId)
      .then((result) => {
        setDetail(result);
        setError(null);
      })
      .catch(() => {
        setError('This customer could not be loaded. Please try again.');
      });
  }, [parsedId]);

  useEffect(() => {
    if (Number.isNaN(parsedId)) {
      setError('Unknown customer.');
      return;
    }
    loadDetail();
  }, [parsedId, loadDetail]);

  if (error !== null) {
    return (
      <main className="customer-detail-page">
        <h2>Customer detail</h2>
        <ErrorMessage message={error} />
      </main>
    );
  }

  if (detail === null) {
    return (
      <main className="customer-detail-page">
        <h2>Customer detail</h2>
        <p className="sub">Loading…</p>
      </main>
    );
  }

  return (
    <main className="customer-detail-page">
      <h2>{detail.email}</h2>
      <p className="sub">Portfolio drill-in — holdings, goals and current allocation on a single screen.</p>

      <section className="panel">
        <h3>Profile</h3>
        <dl className="meta">
          <div>
            <dt>customer_id</dt>
            <dd>{detail.customer_id}</dd>
          </div>
          <div>
            <dt>kyc_verified</dt>
            <dd>{detail.kyc_verified ? 'true' : 'false'}</dd>
          </div>
          <div>
            <dt>risk_band</dt>
            <dd data-testid="customer-risk-band">
              <span className="band-pill">{detail.risk_band ?? 'not assessed'}</span>
            </dd>
          </div>
          <div>
            <dt>rule_version</dt>
            <dd>{detail.rule_version ?? '—'}</dd>
          </div>
        </dl>
        <p style={{ marginTop: 14 }}>
          <button
            type="button"
            className="small"
            data-testid="manual-rec-open"
            onClick={() => setManualRecOpen(true)}
          >
            Log a manual recommendation
          </button>
        </p>
      </section>

      <div className="cols">
        <section className="panel">
          <h3>Holdings</h3>
          {detail.holdings.holdings.length === 0 ? (
            <p className="sub">No holdings.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th scope="col">asset_class_code</th>
                  <th scope="col" className="num">
                    current_value
                  </th>
                  <th scope="col" className="num">
                    drift_percent
                  </th>
                  <th scope="col">exceeds_threshold</th>
                </tr>
              </thead>
              <tbody>
                {detail.holdings.holdings.map((holding) => (
                  <tr key={holding.asset_class_id} data-breach={String(holding.exceeds_threshold)}>
                    <td>
                      <code className="mono">{holding.asset_class_code}</code>
                    </td>
                    <td className="num">{holding.current_value}</td>
                    <td className="num">{formatPercent(holding.drift_percent)}</td>
                    <td>{holding.exceeds_threshold ? 'true' : 'false'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          <h3>Current allocation</h3>
          {detail.allocation === null ? (
            <p className="sub">No active allocation.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th scope="col">asset_class_code</th>
                  <th scope="col">asset_class_name</th>
                  <th scope="col" className="num">
                    percent
                  </th>
                </tr>
              </thead>
              <tbody>
                {detail.allocation.allocations.map((line) => (
                  <tr key={line.asset_class_id}>
                    <td>
                      <code className="mono">{line.asset_class_code}</code>
                    </td>
                    <td>{line.asset_class_name}</td>
                    <td className="num">{formatPercent(line.percent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="panel">
        <h3>Goals</h3>
        {detail.goals.length === 0 ? (
          <p className="sub">No goals.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col" className="num">
                  id
                </th>
                <th scope="col" className="num">
                  target_amount
                </th>
                <th scope="col">target_date</th>
                <th scope="col" className="num">
                  priority
                </th>
                <th scope="col" className="num">
                  percent_complete
                </th>
              </tr>
            </thead>
            <tbody>
              {detail.goals.map((goal) => (
                <tr key={goal.id}>
                  <td className="num">{goal.id}</td>
                  <td className="num">{goal.target_amount}</td>
                  <td>{goal.target_date}</td>
                  <td className="num">{goal.priority}</td>
                  <td className="num">{goal.percent_complete ?? 'null'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h3>Override risk band</h3>
        <p className="sub">
          Append-only and fully audited. previous_band is captured server-side; the form submits
          only new_band, reason and note.
        </p>
        <OverrideForm
          customerId={detail.customer_id}
          currentBand={detail.risk_band}
          onOverridden={loadDetail}
        />
      </section>

      <section className="panel">
        <h3>override_history</h3>
        {detail.override_history.length === 0 ? (
          <p className="sub">No overrides yet.</p>
        ) : (
          <ul data-testid="override-history">
            {detail.override_history.map((entry) => (
              <li key={entry.id}>
                <code className="mono">{entry.previous_band}</code> &rarr;{' '}
                <code className="mono">{entry.new_band}</code> ({entry.created_at}): {entry.reason}
              </li>
            ))}
          </ul>
        )}
      </section>

      {manualRecOpen && (
        <ManualRecommendationModal
          customerId={detail.customer_id}
          onClose={() => setManualRecOpen(false)}
          onLogged={() => setManualRecOpen(false)}
        />
      )}
    </main>
  );
}
