/**
 * Admin allocation-template editor (E10-S4 AC1, AC2, AC5;
 * api-contracts.md §12.4/12.5).
 *
 * The running total and Publish gate go exclusively through
 * lib/money.ts's basis-point helpers — the same basis-point convention the
 * backend's authoritative TEMPLATE_SUM_INVALID check uses
 * (backend/src/domain/admin/service.py's ALLOCATION_TOTAL_BPS = 10000).
 * This screen's gate is a UX convenience in front of that same rule, not an
 * independently-tunable threshold (architecture_check
 * `template_editor_sum_gate_matches_api`).
 */
import { useCallback, useEffect, useState } from 'react';

import type {
  AllocationRequestEntry,
  AllocationTemplateResponse,
  AssetClassResponse,
} from '../../api/admin';
import { getAllocationTemplates, getAssetClasses, publishAllocationTemplate } from '../../api/admin';
import { EmptyState } from '../../components/EmptyState';
import { ErrorMessage } from '../../components/ErrorMessage';
import { formatBpsAsPercent, isExactlyFullPercent, parsePercentToBps, sumBps } from '../../lib/money';
import type { RiskBand } from '../../types/entities';

const RISK_BANDS: RiskBand[] = ['CONSERVATIVE', 'MODERATE', 'AGGRESSIVE'];

function defaultRows(assetClasses: AssetClassResponse[]): AllocationRequestEntry[] {
  return assetClasses.map((assetClass) => ({ asset_class_id: assetClass.id, percent: '0.00' }));
}

export function TemplateEditor() {
  const [assetClasses, setAssetClasses] = useState<AssetClassResponse[]>([]);
  const [riskBand, setRiskBand] = useState<RiskBand>('MODERATE');
  const [rows, setRows] = useState<AllocationRequestEntry[]>([]);
  const [history, setHistory] = useState<AllocationTemplateResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [publishedMessage, setPublishedMessage] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAssetClasses()
      .then((classes) => {
        if (!cancelled) {
          setAssetClasses(classes);
          setRows(defaultRows(classes));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Asset classes could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadHistory = useCallback((band: RiskBand) => {
    getAllocationTemplates(band)
      .then((templates) => setHistory(templates))
      .catch(() => setError('Version history could not be loaded. Please try again.'));
  }, []);

  useEffect(() => {
    loadHistory(riskBand);
  }, [riskBand, loadHistory]);

  function handleRiskBandChange(next: RiskBand): void {
    setRiskBand(next);
    setRows(defaultRows(assetClasses));
    setPublishedMessage(null);
  }

  function handlePercentChange(index: number, value: string): void {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, percent: value } : row)));
  }

  function handleAddRow(): void {
    const firstAssetClass = assetClasses[0];
    if (firstAssetClass === undefined) {
      return;
    }
    setRows((current) => [...current, { asset_class_id: firstAssetClass.id, percent: '0.00' }]);
  }

  function handleRemoveRow(index: number): void {
    setRows((current) => current.filter((_, i) => i !== index));
  }

  function assetClassName(id: number): string {
    return assetClasses.find((assetClass) => assetClass.id === id)?.name ?? '—';
  }

  const bpsValues = rows.map((row) => parsePercentToBps(row.percent));
  const hasInvalidEntry = bpsValues.some((value) => value === null);
  const totalBps = sumBps(bpsValues.map((value) => value ?? 0));
  const totalIsExact = !hasInvalidEntry && isExactlyFullPercent(totalBps);

  async function handlePublish(): Promise<void> {
    if (!totalIsExact) {
      return;
    }
    setError(null);
    setIsPublishing(true);
    try {
      const response = await publishAllocationTemplate({ risk_band: riskBand, allocations: rows });
      setPublishedMessage(`Published version ${response.version} for ${response.risk_band}.`);
      loadHistory(riskBand);
    } catch {
      setError('Publish failed. Please try again.');
    } finally {
      setIsPublishing(false);
    }
  }

  return (
    <main className="admin-page">
      <h2>Allocation template editor</h2>
      <p className="sub">
        Rules and templates are insert-only and immutable once published (AC-10). Publishing
        creates a new version; in-flight customers stay pinned to the version active when they
        were assigned.
      </p>

      {error !== null && <ErrorMessage message={error} />}
      {publishedMessage !== null && (
        <div className="okbox" role="status">
          {publishedMessage}
        </div>
      )}

      <section className="panel">
        <h3>New allocation template</h3>
        <div className="field" style={{ maxWidth: 240 }}>
          <label htmlFor="risk_band">risk_band</label>
          <select
            id="risk_band"
            value={riskBand}
            onChange={(event) => handleRiskBandChange(event.target.value as RiskBand)}
          >
            {RISK_BANDS.map((band) => (
              <option key={band} value={band}>
                {band}
              </option>
            ))}
          </select>
        </div>

        <table>
          <thead>
            <tr>
              <th scope="col">asset class</th>
              <th scope="col" className="num">
                percent
              </th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.asset_class_id}-${index}`}>
                <td>{assetClassName(row.asset_class_id)}</td>
                <td className="num">
                  <label className="sr-only" htmlFor={`allocation-percent-${index}`}>
                    percent for row {index + 1}
                  </label>
                  <input
                    id={`allocation-percent-${index}`}
                    data-testid={`allocation-percent-${index}`}
                    type="text"
                    inputMode="decimal"
                    value={row.percent}
                    onChange={(event) => handlePercentChange(index, event.target.value)}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="secondary small"
                    onClick={() => handleRemoveRow(index)}
                    aria-label={`Remove row ${index + 1}`}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p>
          <button type="button" className="secondary small" onClick={handleAddRow}>
            Add asset class row
          </button>
        </p>

        <div
          className={`total ${totalIsExact ? 'valid' : 'invalid'}`}
          role="status"
          aria-live="polite"
          data-testid="allocation-total"
        >
          <span>Running total</span>
          <b>{formatBpsAsPercent(totalBps)}</b>
          <span>
            {totalIsExact
              ? 'Sums to exactly 100.00 — ready to publish.'
              : 'Must sum to exactly 100.00 before publishing.'}
          </span>
        </div>

        <button type="button" data-testid="publish" disabled={!totalIsExact || isPublishing} onClick={() => void handlePublish()}>
          {isPublishing ? 'Publishing…' : 'Publish new version'}
        </button>
      </section>

      <section className="panel">
        <h3>Version history</h3>
        {history.length === 0 ? (
          <EmptyState message="No templates published for this risk band yet." />
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">id</th>
                <th scope="col" className="num">
                  version
                </th>
                <th scope="col">published_at</th>
                <th scope="col">is_active</th>
              </tr>
            </thead>
            <tbody>
              {history.map((template) => (
                <tr key={template.id}>
                  <td>{template.id}</td>
                  <td className="num">{template.version}</td>
                  <td>{template.published_at}</td>
                  <td>{String(template.is_active)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
