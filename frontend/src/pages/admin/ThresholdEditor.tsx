/**
 * Admin rebalancing-threshold publisher (E10-S4 component-map scaffolding;
 * api-contracts.md §12.9/12.10). Not itself an acceptance criterion this
 * group (contract note 6) — a separate versioned resource from the
 * allocation template, kept intentionally minimal: list the current
 * history, publish a new integer basis-point value.
 */
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';

import type { RebalancingThresholdResponse } from '../../api/admin';
import { getRebalancingThresholds, publishRebalancingThreshold } from '../../api/admin';
import { ErrorMessage } from '../../components/ErrorMessage';

const MIN_THRESHOLD_BPS = 1;
const MAX_THRESHOLD_BPS = 10000;

export function ThresholdEditor() {
  const [history, setHistory] = useState<RebalancingThresholdResponse[]>([]);
  const [thresholdBps, setThresholdBps] = useState('500');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getRebalancingThresholds()
      .then((result) => {
        if (!cancelled) {
          setHistory(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError('Rebalancing thresholds could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setValidationError(null);
    const parsed = Number(thresholdBps);
    if (!Number.isInteger(parsed) || parsed < MIN_THRESHOLD_BPS || parsed > MAX_THRESHOLD_BPS) {
      setValidationError('threshold_bps must be an integer between 1 and 10000.');
      return;
    }
    setIsPublishing(true);
    try {
      const response = await publishRebalancingThreshold({ threshold_bps: parsed });
      setHistory((current) => [...current, response]);
    } catch {
      setValidationError('Publish failed. Please try again.');
    } finally {
      setIsPublishing(false);
    }
  }

  return (
    <main className="admin-page">
      <h2>Rebalancing threshold</h2>
      <p className="sub">
        A separate versioned resource from the allocation template — existing pending
        recommendations keep the threshold they were generated under.
      </p>
      {loadError !== null && <ErrorMessage message={loadError} />}

      <section className="panel">
        <h3>Publish rebalancing threshold</h3>
        {validationError !== null && <ErrorMessage message={validationError} />}
        <form onSubmit={(event) => void handleSubmit(event)} noValidate>
          <div className="row">
            <div className="field" style={{ maxWidth: 200 }}>
              <label htmlFor="threshold_bps">threshold_bps</label>
              <input
                id="threshold_bps"
                type="number"
                min={MIN_THRESHOLD_BPS}
                max={MAX_THRESHOLD_BPS}
                step={1}
                value={thresholdBps}
                onChange={(event) => setThresholdBps(event.target.value)}
              />
            </div>
            <div className="field" style={{ maxWidth: 'none', flex: '0 0 auto' }}>
              <button type="submit" disabled={isPublishing}>
                Publish new version
              </button>
            </div>
          </div>
        </form>
      </section>

      <section className="panel">
        <h3>Version history</h3>
        <table>
          <thead>
            <tr>
              <th scope="col">id</th>
              <th scope="col" className="num">
                version
              </th>
              <th scope="col" className="num">
                threshold_bps
              </th>
              <th scope="col" className="num">
                threshold_percent
              </th>
              <th scope="col">published_at</th>
              <th scope="col">is_active</th>
            </tr>
          </thead>
          <tbody>
            {history.map((row) => (
              <tr key={row.id}>
                <td>{row.id}</td>
                <td className="num">{row.version}</td>
                <td className="num">{row.threshold_bps}</td>
                <td className="num">{row.threshold_percent}</td>
                <td>{row.published_at}</td>
                <td>{String(row.is_active)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
