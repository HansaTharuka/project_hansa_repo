import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import * as goalsApi from '../../api/goals';
import type { GoalResponse } from '../../api/goals';
import { Goals } from './Goals';

const GOAL_WITH_PROGRESS: GoalResponse = {
  id: 7,
  customer_id: 3,
  target_amount: '450000.00',
  target_date: '2041-09-30',
  priority: 1,
  created_at: '2026-04-12T08:31:00Z',
  updated_at: '2026-04-12T08:31:00Z',
  percent_complete: '25.00',
};

const GOAL_WITHOUT_PROGRESS: GoalResponse = {
  id: 12,
  customer_id: 3,
  target_amount: '25000.00',
  target_date: '2028-08-01',
  priority: 3,
  created_at: '2026-06-21T19:45:00Z',
  updated_at: '2026-08-30T11:02:00Z',
  percent_complete: null,
};

async function renderWithGoals(
  goals: GoalResponse[] = [GOAL_WITH_PROGRESS, GOAL_WITHOUT_PROGRESS],
): Promise<void> {
  vi.spyOn(goalsApi, 'getGoals').mockResolvedValue(goals);
  render(<Goals />);
  await waitFor(() => expect(screen.getByTestId(`goal-${goals[0]!.id}`)).toBeInTheDocument());
}

async function renderEmpty(): Promise<void> {
  vi.spyOn(goalsApi, 'getGoals').mockResolvedValue([]);
  render(<Goals />);
  await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
}

describe('Goals', () => {
  it('lists each goal with target_amount, target_date, priority, and percent_complete (AC1)', async () => {
    await renderWithGoals();

    const card = screen.getByTestId('goal-7');
    expect(within(card).getByText('450000.00')).toBeInTheDocument();
    expect(within(card).getByText('2041-09-30')).toBeInTheDocument();
    expect(within(card).getByText('priority: 1')).toBeInTheDocument();
    expect(within(card).getByText('25.00')).toBeInTheDocument();

    const otherCard = screen.getByTestId('goal-12');
    expect(within(otherCard).getByText('25000.00')).toBeInTheDocument();
    expect(within(otherCard).getByText('2028-08-01')).toBeInTheDocument();
    expect(within(otherCard).getByText('priority: 3')).toBeInTheDocument();
  });

  it('shows an explicit empty-state message for a customer with zero goals', async () => {
    await renderEmpty();
    expect(screen.queryByTestId(/^goal-/)).not.toBeInTheDocument();
  });

  it.each(['0', '-500.00'])(
    'shows an inline validation error and never calls the create API when target_amount is %s (AC2)',
    async (invalidAmount) => {
      const createSpy = vi.spyOn(goalsApi, 'createGoal');
      await renderEmpty();

      fireEvent.change(screen.getByLabelText('target_amount'), {
        target: { value: invalidAmount },
      });
      fireEvent.change(screen.getByLabelText('target_date'), {
        target: { value: '2035-01-01' },
      });
      fireEvent.click(screen.getByRole('button', { name: /create goal/i }));

      expect(
        await screen.findByText('target_amount must be greater than 0.'),
      ).toBeInTheDocument();
      expect(createSpy).not.toHaveBeenCalled();
    },
  );

  it('creates a goal with a valid positive target_amount and renders it without a page reload (AC2 happy path)', async () => {
    await renderEmpty();
    const createSpy = vi.spyOn(goalsApi, 'createGoal').mockResolvedValue({
      id: 20,
      customer_id: 3,
      target_amount: '80000.00',
      target_date: '2035-01-01',
      priority: 2,
      created_at: '2026-09-08T12:00:00Z',
      updated_at: '2026-09-08T12:00:00Z',
      percent_complete: null,
    });

    fireEvent.change(screen.getByLabelText('target_amount'), { target: { value: '80000.00' } });
    fireEvent.change(screen.getByLabelText('target_date'), { target: { value: '2035-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /create goal/i }));

    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith({
        target_amount: '80000.00',
        target_date: '2035-01-01',
        priority: 2,
      }),
    );
    expect(await screen.findByTestId('goal-20')).toBeInTheDocument();
  });

  it("renders a progress bar and percentage label reflecting the goal's percent_complete verbatim (AC3)", async () => {
    await renderWithGoals();

    const card = screen.getByTestId('goal-7');
    const bar = within(card).getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '25');
    expect(within(card).getByText('25.00%')).toBeInTheDocument();
  });

  it('shows a "no snapshot yet" label when percent_complete is null (AC3)', async () => {
    await renderWithGoals();

    const card = screen.getByTestId('goal-12');
    const bar = within(card).getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '0');
    expect(within(card).getByText(/no snapshot yet/i)).toBeInTheDocument();
  });

  it("updates a goal's displayed priority after editing and saving, without a page reload (AC4)", async () => {
    await renderWithGoals();
    const updateSpy = vi.spyOn(goalsApi, 'updateGoal').mockResolvedValue({
      ...GOAL_WITH_PROGRESS,
      priority: 3,
      updated_at: '2026-09-08T12:05:00Z',
    });
    const user = userEvent.setup();

    const card = screen.getByTestId('goal-7');
    await user.click(within(card).getByTestId('goal-edit'));

    fireEvent.change(screen.getByLabelText('priority'), { target: { value: '3' } });
    await user.click(screen.getByRole('button', { name: /save priority/i }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith(7, { priority: 3 }));
    await waitFor(() =>
      expect(within(screen.getByTestId('goal-7')).getByText('priority: 3')).toBeInTheDocument(),
    );
    // The create form's fields are still present afterward — proof this was
    // an in-place state update, not a route navigation/full reload.
    expect(screen.getByLabelText('target_amount')).toBeInTheDocument();
  });

  it('every form input is labeled and reachable via keyboard Tab order (AC5)', async () => {
    await renderEmpty();

    const amountInput = screen.getByLabelText('target_amount');
    const dateInput = screen.getByLabelText('target_date');
    const priorityInput = screen.getByLabelText('priority');

    expect(amountInput).toBeInstanceOf(HTMLInputElement);
    expect(dateInput).toBeInstanceOf(HTMLInputElement);
    expect(priorityInput).toBeInstanceOf(HTMLSelectElement);

    const user = userEvent.setup();
    amountInput.focus();
    expect(amountInput).toHaveFocus();
    await user.tab();
    expect(dateInput).toHaveFocus();
    await user.tab();
    expect(priorityInput).toHaveFocus();
  });
});
