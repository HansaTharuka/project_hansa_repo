/**
 * The compliance/auditor read-only audit-log screen (E3-S4 AC1-AC5;
 * BRD §12; api-contracts.md §13.1).
 *
 * Read-only by construction: this component never renders an edit, delete,
 * update, or resolve control — the only buttons are Apply, Clear, and
 * pagination (AC4). All filtering happens server-side via query parameters;
 * this component never re-filters the response it receives (AC2, AC3).
 */
import type { FormEvent } from 'react';
import { useCallback, useEffect, useState } from 'react';

import type { AuditEntryResponse, AuditPageResponse } from '../../api/audit';
import { getAuditEntries } from '../../api/audit';
import { DataTable } from '../../components/DataTable';
import { ErrorMessage } from '../../components/ErrorMessage';
import type { AuditEntityType } from '../../types/entities';

const ENTITY_TYPES: AuditEntityType[] = [
  'RiskBandAssignment',
  'AllocationRecommendation',
  'RebalancingRecommendation',
  'AdvisorOverride',
  'ManualRecommendation',
  'RiskBandRule',
  'AllocationTemplate',
  'AssetClass',
  'RebalancingThreshold',
];

const LIMIT = 50;

interface Filters {
  actorId: string;
  entityType: string;
  from: string;
  to: string;
}

const EMPTY_FILTERS: Filters = { actorId: '', entityType: '', from: '', to: '' };

export function AuditLog() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState<AuditPageResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const runQuery = useCallback(async (current: Filters, currentOffset: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getAuditEntries({
        actor_id: current.actorId === '' ? undefined : Number(current.actorId),
        entity_type: current.entityType === '' ? undefined : current.entityType,
        from: current.from === '' ? undefined : current.from,
        to: current.to === '' ? undefined : current.to,
        limit: LIMIT,
        offset: currentOffset,
      });
      setPage(result);
    } catch {
      setError('Unable to load audit entries. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void runQuery(EMPTY_FILTERS, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setOffset(0);
    void runQuery(filters, 0);
  }

  function handleClear(): void {
    setFilters(EMPTY_FILTERS);
    setOffset(0);
    void runQuery(EMPTY_FILTERS, 0);
  }

  function goToPage(direction: -1 | 1): void {
    const nextOffset = Math.max(0, offset + direction * LIMIT);
    setOffset(nextOffset);
    void runQuery(filters, nextOffset);
  }

  const entries = page?.entries ?? [];
  const total = page?.total ?? 0;

  return (
    <main>
      <h2>Audit log</h2>
      <p className="sub">
        Append-only trail of risk-band assignments, recommendations, rebalancing actions and
        advisor overrides. Read-only — no edit, delete, or resolve control exists on this screen.
      </p>

      <section className="panel">
        <h3>Filters</h3>
        {error !== null && <ErrorMessage message={error} />}
        <form className="filters" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="actor_id">actor_id</label>
            <input
              id="actor_id"
              name="actor_id"
              type="number"
              value={filters.actorId}
              onChange={(event) => setFilters({ ...filters, actorId: event.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="entity_type">entity_type</label>
            <select
              id="entity_type"
              name="entity_type"
              value={filters.entityType}
              onChange={(event) => setFilters({ ...filters, entityType: event.target.value })}
            >
              <option value="">All entity types</option>
              {ENTITY_TYPES.map((entityType) => (
                <option key={entityType} value={entityType}>
                  {entityType}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="from">from (inclusive)</label>
            <input
              id="from"
              name="from"
              type="date"
              value={filters.from}
              onChange={(event) => setFilters({ ...filters, from: event.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="to">to (inclusive)</label>
            <input
              id="to"
              name="to"
              type="date"
              value={filters.to}
              onChange={(event) => setFilters({ ...filters, to: event.target.value })}
            />
          </div>
          <div className="field" style={{ flex: '0 0 auto' }}>
            <button type="submit" disabled={isLoading}>
              Apply
            </button>{' '}
            <button type="button" className="secondary" onClick={handleClear}>
              Clear
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h3>Entries</h3>
        <p className="count">
          {isLoading ? 'Loading…' : `Showing ${entries.length} of ${total} matching entries.`}
        </p>
        <DataTable
          columns={[
            { key: 'id', label: 'id' },
            { key: 'timestamp', label: 'timestamp' },
            { key: 'actor_id', label: 'actor_id' },
            { key: 'actor_role', label: 'actor_role' },
            { key: 'entity_type', label: 'entity_type' },
            { key: 'entity_id', label: 'entity_id' },
            { key: 'action', label: 'action' },
            {
              key: 'details_json',
              label: 'details_json',
              render: (row: AuditEntryResponse) => JSON.stringify(row.details_json),
            },
          ]}
          rows={entries}
          getRowKey={(row) => row.id}
          emptyMessage="No audit entries match these filters."
        />
        <div className="pager">
          <span>
            total {total} · limit {LIMIT} · offset {offset}
          </span>
          <button
            type="button"
            className="secondary"
            onClick={() => goToPage(-1)}
            disabled={offset === 0}
          >
            Previous
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => goToPage(1)}
            disabled={offset + LIMIT >= total}
          >
            Next
          </button>
        </div>
      </section>
    </main>
  );
}
