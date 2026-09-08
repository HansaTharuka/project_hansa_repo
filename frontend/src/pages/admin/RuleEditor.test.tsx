import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as adminApi from '../../api/admin';
import type { RiskBandRuleResponse } from '../../api/admin';
import { RuleEditor } from './RuleEditor';

function buildQuestions(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    question_id: `Q${i + 1}`,
    text: `Sample question ${i + 1}?`,
    options: [
      { value: 'opt_1', label: 'Option 1', points: 1 },
      { value: 'opt_2', label: 'Option 2', points: 2 },
      { value: 'opt_3', label: 'Option 3', points: 3 },
      { value: 'opt_4', label: 'Option 4', points: 4 },
    ],
  }));
}

const FIVE_QUESTION_RULE: RiskBandRuleResponse = {
  id: 2,
  version: 2,
  questionnaire_json: { questions: buildQuestions(5) },
  scoring_rules_json: {
    bands: [
      { risk_band: 'CONSERVATIVE', min_points: 5, max_points: 10 },
      { risk_band: 'MODERATE', min_points: 11, max_points: 15 },
      { risk_band: 'AGGRESSIVE', min_points: 16, max_points: 20 },
    ],
  },
  published_at: '2026-08-01T09:00:00Z',
  is_active: true,
};

async function renderReady() {
  const user = userEvent.setup();
  render(<RuleEditor />);
  await screen.findByText(/5 questions defined/i);
  return user;
}

describe('RuleEditor', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adminApi, 'getRiskBandRules').mockResolvedValue([FIVE_QUESTION_RULE]);
  });

  it('disables Publish while fewer than 6 questions are present', async () => {
    await renderReady();

    expect(screen.getByTestId('rule-publish')).toBeDisabled();
  });

  it('adding a question via Add Question crosses the 6-question threshold and enables Publish', async () => {
    const user = await renderReady();

    await user.click(screen.getByTestId('add-question'));

    await screen.findByText(/6 questions defined/i);
    expect(screen.getByTestId('rule-publish')).toBeEnabled();
  });

  it('removing a question below 6 disables Publish again', async () => {
    const user = await renderReady();
    await user.click(screen.getByTestId('add-question'));
    await screen.findByText(/6 questions defined/i);
    expect(screen.getByTestId('rule-publish')).toBeEnabled();

    const [firstRemoveButton] = screen.getAllByRole('button', { name: /remove question/i });
    if (firstRemoveButton === undefined) {
      throw new Error('expected at least one "Remove question" button');
    }
    await user.click(firstRemoveButton);

    await screen.findByText(/5 questions defined/i);
    expect(screen.getByTestId('rule-publish')).toBeDisabled();
  });

  it('publishing a new version refreshes the version-history list via state update, without navigation', async () => {
    const user = await renderReady();
    await user.click(screen.getByTestId('add-question'));
    await screen.findByText(/6 questions defined/i);

    const publishSpy = vi.spyOn(adminApi, 'publishRiskBandRule').mockResolvedValue({
      id: 3,
      version: 3,
      published_at: '2026-09-05T11:00:00Z',
      is_active: true,
    });

    await user.click(screen.getByTestId('rule-publish'));

    await waitFor(() => expect(publishSpy).toHaveBeenCalledTimes(1));
    const firstCall = publishSpy.mock.calls[0];
    if (firstCall === undefined) {
      throw new Error('expected publishRiskBandRule to have been called');
    }
    expect(firstCall[0].questionnaire_json.questions).toHaveLength(6);
    expect(await screen.findByText('2026-09-05T11:00:00Z')).toBeInTheDocument();
  });

  it('editing a question’s text updates its value', async () => {
    const user = await renderReady();

    const textInput = screen.getByLabelText(/question text for Q1/i);
    await user.clear(textInput);
    await user.type(textInput, 'Updated question text?');

    expect(textInput).toHaveValue('Updated question text?');
  });
});
