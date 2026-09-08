/**
 * Customer goals screen (E7-S5 AC1-AC5; BRD §12; api-contracts.md §9).
 *
 * `target_amount` and `percent_complete` are rendered verbatim from the
 * API's fixed-point decimal string — never round-tripped through
 * `parseFloat`/`toFixed` (NFR-01). The one place this component reads a
 * percent string as a JS number is the progress bar's CSS `width`, which is
 * a display-only layout computation, not money/percent business logic.
 *
 * The create form and the edit-priority form are the same `<form>`,
 * switched by `editingGoalId`: this keeps `id="target_amount"`,
 * `id="target_date"` and `id="priority"` singleton on the page at all
 * times, so there is never a duplicate-id collision between "create a new
 * goal" and "edit an existing goal's priority".
 */
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';

import type { GoalResponse } from '../../api/goals';
import { createGoal, getGoals, updateGoal } from '../../api/goals';
import { EmptyState } from '../../components/EmptyState';
import { ErrorMessage } from '../../components/ErrorMessage';
import { LabeledField } from '../../components/LabeledField';

const PRIORITY_OPTIONS = [1, 2, 3, 4, 5];
const DEFAULT_PRIORITY = '2';

export function Goals() {
  const [goals, setGoals] = useState<GoalResponse[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [amountError, setAmountError] = useState<string | null>(null);

  const [editingGoalId, setEditingGoalId] = useState<number | null>(null);
  const [targetAmount, setTargetAmount] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [priority, setPriority] = useState(DEFAULT_PRIORITY);

  useEffect(() => {
    let cancelled = false;
    getGoals()
      .then((result) => {
        if (!cancelled) {
          setGoals(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError('Goals could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function startEdit(goal: GoalResponse): void {
    setEditingGoalId(goal.id);
    setPriority(String(goal.priority));
    setSubmitError(null);
  }

  function resetForm(): void {
    setEditingGoalId(null);
    setTargetAmount('');
    setTargetDate('');
    setPriority(DEFAULT_PRIORITY);
    setAmountError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSubmitError(null);

    if (editingGoalId !== null) {
      await submitPriorityEdit(editingGoalId);
      return;
    }
    await submitCreate();
  }

  async function submitPriorityEdit(goalId: number): Promise<void> {
    try {
      const updated = await updateGoal(goalId, { priority: Number(priority) });
      setGoals((current) =>
        (current ?? []).map((goal) => (goal.id === updated.id ? updated : goal)),
      );
      resetForm();
    } catch {
      setSubmitError('Could not save the updated priority. Please try again.');
    }
  }

  async function submitCreate(): Promise<void> {
    if (!(Number(targetAmount) > 0)) {
      setAmountError('target_amount must be greater than 0.');
      return;
    }
    setAmountError(null);

    try {
      const created = await createGoal({
        target_amount: targetAmount,
        target_date: targetDate,
        priority: Number(priority),
      });
      setGoals((current) => [...(current ?? []), created]);
      resetForm();
    } catch {
      setSubmitError('Could not create the goal. Please try again.');
    }
  }

  return (
    <main className="goals-page">
      <h2>My goals</h2>
      <p className="sub">
        Each goal tracks target_amount. percent_complete comes from the latest
        GoalProgressSnapshot and is null until the first snapshot exists.
      </p>

      <section className="panel">
        <h3>{editingGoalId === null ? 'Create a goal' : `Edit goal #${editingGoalId} priority`}</h3>
        {submitError !== null && <ErrorMessage message={submitError} />}
        <form onSubmit={(event) => void handleSubmit(event)} noValidate>
          {editingGoalId === null && (
            <>
              <LabeledField
                id="target_amount"
                label="target_amount"
                type="number"
                step="0.01"
                min="0.01"
                value={targetAmount}
                onChange={setTargetAmount}
                error={amountError ?? undefined}
              />
              <LabeledField
                id="target_date"
                label="target_date"
                type="date"
                value={targetDate}
                onChange={setTargetDate}
              />
            </>
          )}
          <div className="field">
            <label htmlFor="priority">priority</label>
            <select
              id="priority"
              name="priority"
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
            >
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <button type="submit">{editingGoalId === null ? 'Create goal' : 'Save priority'}</button>
          {editingGoalId !== null && (
            <button type="button" onClick={resetForm}>
              Cancel
            </button>
          )}
        </form>
      </section>

      <section className="panel">
        <h3>Goals</h3>
        {loadError !== null && <ErrorMessage message={loadError} />}
        {loadError === null && goals === null && <p className="sub">Loading…</p>}
        {loadError === null && goals !== null && goals.length === 0 && (
          <EmptyState message="You have no goals yet." />
        )}
        {loadError === null && goals !== null && goals.length > 0 && (
          <div className="goal-list">
            {goals.map((goal) => (
              <GoalCard key={goal.id} goal={goal} onEdit={startEdit} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function GoalCard({
  goal,
  onEdit,
}: {
  goal: GoalResponse;
  onEdit: (goal: GoalResponse) => void;
}) {
  const width = progressBarWidth(goal.percent_complete);
  return (
    <article className="goal" data-testid={`goal-${goal.id}`}>
      <header>
        <h4>Goal #{goal.id}</h4>
        <span className="prio">priority: {goal.priority}</span>
      </header>
      <dl className="g">
        <div>
          <dt>target_amount</dt>
          <dd>{goal.target_amount}</dd>
        </div>
        <div>
          <dt>target_date</dt>
          <dd>{goal.target_date}</dd>
        </div>
        <div>
          <dt>priority</dt>
          <dd>{goal.priority}</dd>
        </div>
        <div>
          <dt>percent_complete</dt>
          <dd>{goal.percent_complete ?? 'null'}</dd>
        </div>
      </dl>
      <div
        className="bar"
        role="progressbar"
        aria-valuenow={width}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Goal ${goal.id} percent complete`}
      >
        <span style={{ display: 'block', height: '100%', width: `${width}%` }} />
      </div>
      <p className="barlabel">
        percent_complete:{' '}
        <strong>
          {goal.percent_complete === null ? 'null — no snapshot yet' : `${goal.percent_complete}%`}
        </strong>
      </p>
      <button type="button" data-testid="goal-edit" onClick={() => onEdit(goal)}>
        Edit priority
      </button>
    </article>
  );
}

/** Display-only layout computation for the progress bar's CSS width — not a
 * money/percent business calculation. `percent_complete` itself is always
 * rendered verbatim as text (NFR-01); this only clamps a numeric width. */
function progressBarWidth(percentComplete: string | null): number {
  if (percentComplete === null) {
    return 0;
  }
  const parsed = Number(percentComplete);
  if (Number.isNaN(parsed)) {
    return 0;
  }
  return Math.min(100, Math.max(0, parsed));
}
