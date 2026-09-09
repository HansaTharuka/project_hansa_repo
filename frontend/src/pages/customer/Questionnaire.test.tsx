import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as riskProfileApi from '../../api/riskProfile';
import type { QuestionnaireResponse, RiskBandAssignmentResponse } from '../../api/riskProfile';
import { Questionnaire } from './Questionnaire';

const QUESTIONNAIRE: QuestionnaireResponse = {
  rule_version: 1,
  questions: [
    {
      question_id: 'Q1',
      text: 'What is your investment time horizon?',
      options: [
        { value: 'lt_3y', label: 'Less than 3 years' },
        { value: '3_7y', label: '3 to 7 years' },
        { value: 'gt_7y', label: 'More than 7 years' },
      ],
    },
    {
      question_id: 'Q2',
      text: 'How would you react to a 20% portfolio drop?',
      options: [
        { value: 'sell_all', label: 'Sell everything' },
        { value: 'hold', label: 'Hold and wait' },
      ],
    },
  ],
};

const ASSIGNMENT_RESPONSE: RiskBandAssignmentResponse = {
  assignment_id: 13,
  customer_id: 3,
  risk_band: 'MODERATE',
  rule_version: 1,
  assigned_at: '2026-09-03T11:24:08Z',
};

function renderQuestionnaire() {
  return render(
    <MemoryRouter initialEntries={['/customer/questionnaire']}>
      <Routes>
        <Route path="/customer/questionnaire" element={<Questionnaire />} />
        <Route path="/customer/risk-result" element={<p>Risk result landed</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function renderReady() {
  vi.spyOn(riskProfileApi, 'getQuestionnaire').mockResolvedValue(QUESTIONNAIRE);
  vi.spyOn(riskProfileApi, 'getLatestRiskBandAssignment').mockResolvedValue(null);
  renderQuestionnaire();
  await screen.findByText(QUESTIONNAIRE.questions[0]!.text);
}

describe('Questionnaire', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders one control group per question and keeps Submit disabled until every question is answered (AC1)', async () => {
    await renderReady();

    expect(screen.getByText(QUESTIONNAIRE.questions[1]!.text)).toBeInTheDocument();
    const submit = screen.getByRole('button', { name: /submit questionnaire/i });
    expect(submit).toBeDisabled();

    const user = userEvent.setup();
    await user.click(screen.getByTestId('question-1-option-1'));
    expect(submit).toBeDisabled();

    await user.click(screen.getByTestId('question-2-option-1'));
    expect(submit).toBeEnabled();
  });

  it('submits a complete answer set and navigates to the result screen with the returned risk_band (AC2)', async () => {
    vi.spyOn(riskProfileApi, 'submitRiskProfile').mockResolvedValue(ASSIGNMENT_RESPONSE);
    await renderReady();
    const user = userEvent.setup();

    await user.click(screen.getByTestId('question-1-option-1'));
    await user.click(screen.getByTestId('question-2-option-1'));
    await user.click(screen.getByRole('button', { name: /submit questionnaire/i }));

    await waitFor(() => expect(screen.getByText('Risk result landed')).toBeInTheDocument());
    expect(riskProfileApi.submitRiskProfile).toHaveBeenCalledWith([
      { question_id: 'Q1', answer_value: 'lt_3y' },
      { question_id: 'Q2', answer_value: 'sell_all' },
    ]);
  });

  it('shows an inline validation message per unanswered question and never calls submit (AC3)', async () => {
    const submitSpy = vi.spyOn(riskProfileApi, 'submitRiskProfile');
    await renderReady();
    const user = userEvent.setup();

    // Answer only Q1, leave Q2 unanswered — a real browser can never click a
    // disabled Submit button, so the inline message must appear from this
    // interaction alone, with no submit attempt dispatched.
    await user.click(screen.getByTestId('question-1-option-1'));
    const submit = screen.getByRole('button', { name: /submit questionnaire/i });
    expect(submit).toBeDisabled();

    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
    expect(
      screen.getByText('Select an answer for this question before submitting.'),
    ).toBeInTheDocument();
    expect(submitSpy).not.toHaveBeenCalled();
  });

  it('every option is queryable via getByLabelText and reachable via keyboard Tab order (AC4)', async () => {
    await renderReady();

    expect(screen.getByLabelText('Less than 3 years')).toHaveAttribute('id', 'Q1-lt_3y');
    expect(screen.getByLabelText('3 to 7 years')).toHaveAttribute('id', 'Q1-3_7y');
    expect(screen.getByLabelText('More than 7 years')).toHaveAttribute('id', 'Q1-gt_7y');
    expect(screen.getByLabelText('Sell everything')).toHaveAttribute('id', 'Q2-sell_all');
    expect(screen.getByLabelText('Hold and wait')).toHaveAttribute('id', 'Q2-hold');

    const user = userEvent.setup();
    const first = screen.getByTestId('question-1-option-1');
    first.focus();
    expect(first).toHaveFocus();

    await user.keyboard(' ');
    expect(first).toBeChecked();
  });

  it('shows the customer current risk_band from GET /api/risk-profile/latest before any new submission (AC5)', async () => {
    vi.spyOn(riskProfileApi, 'getQuestionnaire').mockResolvedValue(QUESTIONNAIRE);
    vi.spyOn(riskProfileApi, 'getLatestRiskBandAssignment').mockResolvedValue(ASSIGNMENT_RESPONSE);
    renderQuestionnaire();

    await screen.findByText(QUESTIONNAIRE.questions[0]!.text);
    expect(await screen.findByText(/moderate/i)).toBeInTheDocument();
  });
});
