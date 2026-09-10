/**
 * Manual-recommendation logging modal (E9-S4 AC5; api-contracts.md §11.4) —
 * launched from CustomerDetail.tsx's own tree, never a route (BRD §5.1).
 * `note` is the only field the advisor supplies; `customer_id` comes from
 * the prop (sourced from the URL param, not user input) and `advisor_id`
 * from the JWT server-side.
 */
import type { FormEvent } from 'react';
import { useState } from 'react';

import { postManualRecommendation } from '../../api/advisor';
import { ApiError } from '../../api/client';
import { Modal } from '../../components/Modal';

interface ManualRecommendationModalProps {
  customerId: number;
  onClose: () => void;
  onLogged: () => void;
}

export function ManualRecommendationModal({
  customerId,
  onClose,
  onLogged,
}: ManualRecommendationModalProps) {
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (note.trim().length === 0) {
      setError('note is required — the API is not called without it.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await postManualRecommendation(customerId, note);
      onLogged();
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Could not log this recommendation. Please try again.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Log a manual recommendation" onClose={onClose}>
      <p className="sub">Recorded as an audit-only event — no new record is created.</p>
      <form onSubmit={(event) => void handleSubmit(event)} noValidate>
        <div className="field">
          <label htmlFor="manual-rec-note">
            note{' '}
            <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>
              (1–2000 characters)
            </span>
          </label>
          <textarea
            id="manual-rec-note"
            data-testid="manual-rec-note"
            placeholder="Recommendation given to the client and the rationale for it"
            value={note}
            aria-invalid={error !== null ? true : undefined}
            aria-describedby={error !== null ? 'manual-rec-note-error' : undefined}
            onChange={(event) => setNote(event.target.value)}
          />
          {error !== null && (
            <p className="err" role="alert" id="manual-rec-note-error">
              {error}
            </p>
          )}
        </div>
        <button type="submit" data-testid="manual-rec-submit" disabled={submitting}>
          {submitting ? 'Logging…' : 'Log recommendation'}
        </button>
        <button type="button" className="secondary" onClick={onClose}>
          Cancel
        </button>
      </form>
    </Modal>
  );
}
