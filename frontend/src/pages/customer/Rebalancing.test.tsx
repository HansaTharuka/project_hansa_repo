import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/client';
import * as rebalancingApi from '../../api/rebalancing';
import type { RebalancingRecommendation, ResolveRebalancingResponse } from '../../api/rebalancing';
import { Rebalancing } from './Rebalancing';

function nth<T>(items: readonly T[], index: number): T {
  const item = items[index];
  if (item === undefined) {
    throw new Error(`Expected an item at index ${index}, found none.`);
  }
  return item;
}

const FIRST_RECOMMENDATION: RebalancingRecommendation = {
  recommendation_id: 'b6f0c2a4-1d3e-4f58-9a71-0c2e5d8b7a10',
  status: 'pending',
  generated_at: '2026-09-04T08:00:00Z',
  resolved_at: null,
  threshold_bps: 500,
  proposed_actions: [
    {
      asset_class_id: 1,
      asset_class_code: 'EQ_DM',
      action: 'SELL',
      amount: '9065.00',
      units: '24.1600',
      drift_percent: '6.11',
    },
    {
      asset_class_id: 3,
      asset_class_code: 'FI_GOV',
      action: 'BUY',
      amount: '6883.00',
      units: '58.7400',
      drift_percent: '-4.64',
    },
  ],
};

const SECOND_RECOMMENDATION: RebalancingRecommendation = {
  recommendation_id: '3f21ad9c-77b4-4e0a-8c15-6ba2e4d09f37',
  status: 'pending',
  generated_at: '2026-09-04T08:00:00Z',
  resolved_at: null,
  threshold_bps: 500,
  proposed_actions: [
    {
      asset_class_id: 6,
      asset_class_code: 'CASH',
      action: 'SELL',
      amount: '1243.00',
      units: '12.4300',
      drift_percent: '0.85',
    },
  ],
};

const RECOMMENDATIONS: RebalancingRecommendation[] = [FIRST_RECOMMENDATION, SECOND_RECOMMENDATION];

function resolveResponseFor(
  recommendation: RebalancingRecommendation,
  status: 'accepted' | 'dismissed'
): ResolveRebalancingResponse {
  return {
    recommendation_id: recommendation.recommendation_id,
    status,
    resolved_at: '2026-09-04T09:12:00Z',
  };
}

async function renderPopulated(): Promise<void> {
  vi.spyOn(rebalancingApi, 'getRebalancingRecommendations').mockResolvedValue(RECOMMENDATIONS);
  render(<Rebalancing />);
  await waitFor(() => expect(screen.getAllByTestId('recommendation')).toHaveLength(2));
}

describe('Rebalancing', () => {
  it('lists every pending recommendation with its proposed_actions, each showing asset_class and a BUY/SELL label', async () => {
    await renderPopulated();

    const cards = screen.getAllByTestId('recommendation');
    const firstCard = within(nth(cards, 0));
    expect(firstCard.getByText('EQ_DM')).toBeInTheDocument();
    expect(firstCard.getByText('SELL')).toBeInTheDocument();
    expect(firstCard.getByText('FI_GOV')).toBeInTheDocument();
    expect(firstCard.getByText('BUY')).toBeInTheDocument();

    const secondCard = within(nth(cards, 1));
    expect(secondCard.getByText('CASH')).toBeInTheDocument();
    expect(secondCard.getByText('SELL')).toBeInTheDocument();
  });

  it('calls the accept API and removes the recommendation from the pending list on 200 success', async () => {
    const user = userEvent.setup();
    await renderPopulated();
    vi.spyOn(rebalancingApi, 'acceptRebalancingRecommendation').mockResolvedValue(
      resolveResponseFor(FIRST_RECOMMENDATION, 'accepted')
    );

    const acceptButton = nth(screen.getAllByTestId('recommendation-accept'), 0);
    await user.click(acceptButton);

    expect(rebalancingApi.acceptRebalancingRecommendation).toHaveBeenCalledWith(
      FIRST_RECOMMENDATION.recommendation_id
    );
    await waitFor(() => expect(screen.getAllByTestId('recommendation')).toHaveLength(1));
    expect(screen.queryByText('EQ_DM')).not.toBeInTheDocument();
    expect(screen.getByText('CASH')).toBeInTheDocument();
  });

  it('calls the dismiss API and removes the recommendation from the pending list on 200 success', async () => {
    const user = userEvent.setup();
    await renderPopulated();
    vi.spyOn(rebalancingApi, 'dismissRebalancingRecommendation').mockResolvedValue(
      resolveResponseFor(SECOND_RECOMMENDATION, 'dismissed')
    );

    const dismissButton = nth(screen.getAllByTestId('recommendation-dismiss'), 1);
    await user.click(dismissButton);

    expect(rebalancingApi.dismissRebalancingRecommendation).toHaveBeenCalledWith(
      SECOND_RECOMMENDATION.recommendation_id
    );
    await waitFor(() => expect(screen.getAllByTestId('recommendation')).toHaveLength(1));
    expect(screen.queryByText('CASH')).not.toBeInTheDocument();
  });

  it('shows an explicit empty-state message, never a blank/broken layout, when there are no pending recommendations', async () => {
    vi.spyOn(rebalancingApi, 'getRebalancingRecommendations').mockResolvedValue([]);
    render(<Rebalancing />);

    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
    expect(screen.queryByTestId('recommendation')).not.toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('triggers Accept via the keyboard (Enter) exactly like a click', async () => {
    const user = userEvent.setup();
    await renderPopulated();
    vi.spyOn(rebalancingApi, 'acceptRebalancingRecommendation').mockResolvedValue(
      resolveResponseFor(FIRST_RECOMMENDATION, 'accepted')
    );

    const acceptButton = nth(screen.getAllByTestId('recommendation-accept'), 0);
    acceptButton.focus();
    await user.keyboard('{Enter}');

    expect(rebalancingApi.acceptRebalancingRecommendation).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getAllByTestId('recommendation')).toHaveLength(1));
  });

  it('disables Accept/Dismiss immediately on click, before the API promise resolves, and a second immediate click issues no second request', async () => {
    const user = userEvent.setup();
    await renderPopulated();

    let resolveAccept: (value: ResolveRebalancingResponse) => void = () => {
      throw new Error('resolveAccept was not assigned');
    };
    const pending = new Promise<ResolveRebalancingResponse>((resolve) => {
      resolveAccept = resolve;
    });
    vi.spyOn(rebalancingApi, 'acceptRebalancingRecommendation').mockReturnValue(pending);

    const acceptButton = nth(screen.getAllByTestId('recommendation-accept'), 0);
    const dismissButton = nth(screen.getAllByTestId('recommendation-dismiss'), 0);

    await user.click(acceptButton);

    // Both buttons on this row are disabled while the accept call is in flight.
    expect(acceptButton).toBeDisabled();
    expect(dismissButton).toBeDisabled();

    // A second immediate click/press on the now-disabled button is a no-op.
    await user.click(acceptButton);
    await user.keyboard('{Enter}');
    expect(rebalancingApi.acceptRebalancingRecommendation).toHaveBeenCalledTimes(1);

    resolveAccept(resolveResponseFor(FIRST_RECOMMENDATION, 'accepted'));

    await waitFor(() => expect(screen.getAllByTestId('recommendation')).toHaveLength(1));
  });

  it('re-enables the row and shows an inline error when the accept call fails, without removing the recommendation', async () => {
    const user = userEvent.setup();
    await renderPopulated();
    vi.spyOn(rebalancingApi, 'acceptRebalancingRecommendation').mockRejectedValue(
      new ApiError(409, 'ALREADY_RESOLVED', 'This recommendation has already been resolved.')
    );

    const acceptButton = nth(screen.getAllByTestId('recommendation-accept'), 0);
    await user.click(acceptButton);

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/already been resolved/i));
    expect(screen.getAllByTestId('recommendation')).toHaveLength(2);
    expect(acceptButton).not.toBeDisabled();
  });
});
