/**
 * Customer holdings-and-drift view (E6-S5 AC1-AC5; BRD §12;
 * api-contracts.md §8.1).
 *
 * All money/percent values are rendered verbatim from the API's fixed-point
 * string representation — never round-tripped through a JS `number` via
 * `parseFloat`/`toFixed` (AC4, NFR-01). The table collapses to a stacked
 * card list at viewport widths <= 768px via CSS only (BRD §5.3) — both
 * layouts render from the same data, so there is nothing to keep in sync.
 */
import { useEffect, useState } from 'react';

import type { HoldingLineResponse, HoldingsResponse } from '../../api/holdings';
import { getHoldings } from '../../api/holdings';
import { EmptyState } from '../../components/EmptyState';
import { ErrorMessage } from '../../components/ErrorMessage';

export function Holdings() {
  const [data, setData] = useState<HoldingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHoldings()
      .then((result) => {
        if (!cancelled) {
          setData(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Holdings could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error !== null) {
    return (
      <main>
        <h2>Holdings &amp; drift</h2>
        <ErrorMessage message={error} />
      </main>
    );
  }

  if (data === null) {
    return (
      <main>
        <h2>Holdings &amp; drift</h2>
        <p className="sub">Loading…</p>
      </main>
    );
  }

  return (
    <main className="holdings-page">
      <h2>Holdings &amp; drift</h2>
      <p className="sub">
        Your current positions against your target allocation, valued at the latest NAV snapshot.
      </p>

      <section className="panel">
        <h3>Portfolio summary</h3>
        <dl className="summary">
          <div>
            <dt>total_value</dt>
            <dd>{data.total_value}</dd>
          </div>
          <div>
            <dt>as_of_date</dt>
            <dd>{data.as_of_date ?? '—'}</dd>
          </div>
          <div>
            <dt>threshold_percent</dt>
            <dd>{data.threshold_percent}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <h3>By asset class</h3>
        {data.holdings.length === 0 ? (
          <EmptyState message="You have no holdings yet." />
        ) : (
          <>
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">asset_class_code</th>
                    <th scope="col" className="num">
                      current_value
                    </th>
                    <th scope="col" className="num">
                      current_percent
                    </th>
                    <th scope="col" className="num">
                      target_percent
                    </th>
                    <th scope="col" className="num">
                      drift_percent
                    </th>
                    <th scope="col">exceeds_threshold</th>
                  </tr>
                </thead>
                <tbody>
                  {data.holdings.map((holding) => (
                    <tr key={holding.asset_class_id} data-breach={String(holding.exceeds_threshold)}>
                      <td>{holding.asset_class_code}</td>
                      <td className="num">{holding.current_value}</td>
                      <td className="num">{holding.current_percent}</td>
                      <td className="num">{holding.target_percent}</td>
                      <td className="num drift">{holding.drift_percent}</td>
                      <td>{holding.exceeds_threshold ? 'true' : 'false'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="cards" aria-label="Holdings, narrow-viewport layout">
              {data.holdings.map((holding) => (
                <HoldingCard key={holding.asset_class_id} holding={holding} />
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function HoldingCard({ holding }: { holding: HoldingLineResponse }) {
  return (
    <article className="card" data-breach={String(holding.exceeds_threshold)}>
      <h4>{holding.asset_class_code}</h4>
      <dl>
        <div>
          <dt>current_value</dt>
          <dd>{holding.current_value}</dd>
        </div>
        <div>
          <dt>current_percent</dt>
          <dd>{holding.current_percent}</dd>
        </div>
        <div>
          <dt>target_percent</dt>
          <dd>{holding.target_percent}</dd>
        </div>
        <div>
          <dt>drift_percent</dt>
          <dd>{holding.drift_percent}</dd>
        </div>
      </dl>
    </article>
  );
}
