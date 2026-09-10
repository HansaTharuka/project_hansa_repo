/**
 * Risk-band override form (E9-S4 AC3-AC4; api-contracts.md §11.3) — a
 * sub-component of CustomerDetail.tsx's drill-in view, never its own route.
 *
 * `reason` is validated client-side before the API is ever called (AC3):
 * a blank reason shows an inline error next to the field and issues no
 * `POST .../override` request. On success, `onOverridden` lets the parent
 * refetch the drill-in payload so the displayed risk_band and
 * override_history update via state, with no navigation (AC4).
 */
import type { FormEvent } from 'react';
import { useState } from 'react';

import { overrideRiskBand } from '../../api/advisor';
import { ApiError } from '../../api/client';
import type { RiskBand } from '../../types/entities';

const RISK_BANDS: RiskBand[] = ['CONSERVATIVE', 'MODERATE', 'AGGRESSIVE'];

interface OverrideFormProps {
  customerId: number;
  currentBand: RiskBand | null;
  onOverridden: () => void;
}

export function OverrideForm({ customerId, currentBand, onOverridden }: OverrideFormProps) {
  const [newBand, setNewBand] = useState<RiskBand>(currentBand ?? 'MODERATE');
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (reason.trim().length === 0) {
      setReasonError('reason is required — the override API is not called without it.');
      return;
    }
    setReasonError(null);
    setSubmitError(null);
    setSubmitting(true);
    try {
      await overrideRiskBand(customerId, {
        new_band: newBand,
        reason,
        note: note.trim().length > 0 ? note : undefined,
      });
      setReason('');
      setNote('');
      onOverridden();
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Could not submit the override. Please try again.';
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} noValidate className="override-form">
      <div className="field">
        <label htmlFor="new_band">new_band</label>
        <select
          id="new_band"
          name="new_band"
          value={newBand}
          onChange={(event) => setNewBand(event.target.value as RiskBand)}
        >
          {RISK_BANDS.map((band) => (
            <option key={band} value={band}>
              {band}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="reason">
          reason <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>(required)</span>
        </label>
        <input
          id="reason"
          name="reason"
          type="text"
          placeholder="e.g. Client reported imminent liquidity need"
          value={reason}
          aria-invalid={reasonError !== null ? true : undefined}
          aria-describedby={reasonError !== null ? 'reason-error' : undefined}
          onChange={(event) => setReason(event.target.value)}
        />
        {reasonError !== null && (
          <p className="err" role="alert" id="reason-error">
            {reasonError}
          </p>
        )}
      </div>
      <div className="field">
        <label htmlFor="note">
          note <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>(optional)</span>
        </label>
        <textarea
          id="note"
          name="note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
      {submitError !== null && (
        <p className="err" role="alert">
          {submitError}
        </p>
      )}
      <button type="submit" data-testid="override-submit" disabled={submitting}>
        {submitting ? 'Submitting…' : 'Submit override'}
      </button>
    </form>
  );
}
