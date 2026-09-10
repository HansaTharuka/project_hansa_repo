/**
 * Customer recommended-allocation view (E5-S4 AC1-AC5; BRD §12;
 * api-contracts.md §7.1).
 *
 * Individual `percent` values arrive from the API already as 2-decimal-place
 * fixed-point strings, but the *rendered total* (AC1, AC4) is computed
 * client-side by summing basis points through `lib/money.ts`'s integer-safe
 * helpers, never `parseFloat`/`toFixed` (NFR-01) — it must be a genuine
 * client-side sum of the rendered rows, not an echo of the API's
 * `total_percent` field.
 *
 * The view refetches whenever the window regains focus or becomes visible
 * again (AC5) — e.g. after an advisor override lands in another tab — with
 * no full-page reload. A brief notice highlights the refetch when the
 * risk_band actually changed, matching the mockup's refetch feedback.
 */
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '../../api/client';
import type { AllocationEntryResponse, RecommendationResponse } from '../../api/recommendation';
import { getRecommendation } from '../../api/recommendation';
import { ErrorMessage } from '../../components/ErrorMessage';
import { formatBpsAsPercent, parsePercentToBps, sumBps } from '../../lib/money';

function formatPercent(raw: string): string {
  const bps = parsePercentToBps(raw);
  return bps === null ? raw : formatBpsAsPercent(bps);
}

function computeTotal(allocations: readonly AllocationEntryResponse[]): string {
  const bpsValues = allocations.map((line) => parsePercentToBps(line.percent) ?? 0);
  return formatBpsAsPercent(sumBps(bpsValues));
}

/** Display-only layout computation for the share bar's CSS width — not a
 * money/percent business calculation. `percent` itself is always rendered
 * verbatim as formatted text (NFR-01); this only clamps a numeric width,
 * the same exception documented in Goals.tsx's `progressBarWidth`. */
function barWidthPercent(percent: string): number {
  const bps = parsePercentToBps(percent);
  if (bps === null) {
    return 0;
  }
  return Math.min(100, Math.max(0, bps / 100));
}

export function Allocation() {
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [noRiskBand, setNoRiskBand] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justRefetched, setJustRefetched] = useState(false);
  const previousBandRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    function load(): void {
      getRecommendation()
        .then((result) => {
          if (cancelled) {
            return;
          }
          const bandChanged =
            previousBandRef.current !== null && previousBandRef.current !== result.risk_band;
          previousBandRef.current = result.risk_band;
          setData(result);
          setNoRiskBand(false);
          setError(null);
          setJustRefetched(bandChanged);
        })
        .catch((caught: unknown) => {
          if (cancelled) {
            return;
          }
          if (caught instanceof ApiError && caught.code === 'NO_RISK_BAND_ASSIGNMENT') {
            setNoRiskBand(true);
            setData(null);
            setError(null);
            return;
          }
          setError('Your recommended allocation could not be loaded. Please try again.');
        });
    }

    load();
    window.addEventListener('focus', load);
    document.addEventListener('visibilitychange', load);
    return () => {
      cancelled = true;
      window.removeEventListener('focus', load);
      document.removeEventListener('visibilitychange', load);
    };
  }, []);

  if (noRiskBand) {
    return (
      <main className="allocation-page">
        <h2>Recommended allocation</h2>
        <section className="panel">
          <div data-testid="no-risk-band-prompt">
            <p>
              <strong>You do not have a risk band yet.</strong>
            </p>
            <p>
              Complete the risk-profile questionnaire and your recommended allocation will appear
              here. No default or fallback allocation is shown.
            </p>
            <p style={{ marginTop: 18 }}>
              <Link to="/customer/questionnaire" className="btn-link">
                Complete the risk-profile questionnaire
              </Link>
            </p>
          </div>
        </section>
      </main>
    );
  }

  if (error !== null) {
    return (
      <main className="allocation-page">
        <h2>Recommended allocation</h2>
        <ErrorMessage message={error} />
      </main>
    );
  }

  if (data === null) {
    return (
      <main className="allocation-page">
        <h2>Recommended allocation</h2>
        <p className="sub">Loading…</p>
      </main>
    );
  }

  const total = computeTotal(data.allocations);

  return (
    <main className="allocation-page">
      <h2>Recommended allocation</h2>
      <p className="sub">
        Deterministic, rule-based allocation for your risk band and goal horizon.
      </p>

      {justRefetched && (
        <div className="notice" role="status">
          Your risk_band changed to <strong>{data.risk_band}</strong> following an advisor
          override. The allocation below was refetched and re-rendered without a page reload.
        </div>
      )}

      <section className="panel">
        <h3>Basis for this recommendation</h3>
        <dl className="meta">
          <div>
            <dt>risk_band</dt>
            <dd>{data.risk_band}</dd>
          </div>
          <div>
            <dt>rule_version</dt>
            <dd>{data.rule_version}</dd>
          </div>
          <div>
            <dt>template_version</dt>
            <dd>{data.template_version}</dd>
          </div>
          <div>
            <dt>horizon</dt>
            <dd>{data.horizon}</dd>
          </div>
          <div>
            <dt>generated_at</dt>
            <dd>{data.generated_at}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <h3>Target allocation by asset class</h3>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th scope="col">asset_class_code</th>
                <th scope="col">asset_class_name</th>
                <th scope="col" style={{ width: 150 }}>
                  Share
                </th>
                <th scope="col" className="num">
                  percent
                </th>
              </tr>
            </thead>
            <tbody>
              {data.allocations.map((line) => (
                <tr key={line.asset_class_id}>
                  <td>
                    <code className="mono">{line.asset_class_code}</code>
                  </td>
                  <td>{line.asset_class_name}</td>
                  <td>
                    <span className="bar" role="img" aria-label={`${line.percent} percent`}>
                      <i style={{ width: `${barWidthPercent(line.percent)}%` }} />
                    </span>
                  </td>
                  <td className="num">{formatPercent(line.percent)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>Total</td>
                <td className="num" data-testid="allocation-total">
                  {total}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </main>
  );
}
