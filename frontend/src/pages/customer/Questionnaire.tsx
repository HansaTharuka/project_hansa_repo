/**
 * Customer risk-profile questionnaire (E4-S4 AC1-AC5; BRD §12;
 * api-contracts.md §6.1-6.3).
 *
 * `data-testid="question-{n}-option-{m}"` (1-indexed) on every radio is the
 * contract this story's playwright/unit checks target directly.
 */
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { QuestionnaireResponse, RiskBandAssignmentResponse } from '../../api/riskProfile';
import {
  formatRiskBand,
  getLatestRiskBandAssignment,
  getQuestionnaire,
  submitRiskProfile,
} from '../../api/riskProfile';
import { ErrorMessage } from '../../components/ErrorMessage';

export function Questionnaire() {
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireResponse | null>(null);
  const [latest, setLatest] = useState<RiskBandAssignmentResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [invalidQuestionIds, setInvalidQuestionIds] = useState<ReadonlySet<string>>(new Set());
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    getQuestionnaire()
      .then((result) => {
        if (!cancelled) {
          setQuestionnaire(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError('The questionnaire could not be loaded. Please try again.');
        }
      });
    getLatestRiskBandAssignment()
      .then((result) => {
        if (!cancelled) {
          setLatest(result);
        }
      })
      .catch(() => {
        // Supplementary context only (AC5) — a failure here must never block
        // the questionnaire itself from being answered and submitted.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function selectAnswer(questionId: string, value: string): void {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    setInvalidQuestionIds((prev) => {
      if (!prev.has(questionId)) {
        return prev;
      }
      const next = new Set(prev);
      next.delete(questionId);
      return next;
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (questionnaire === null) {
      return;
    }

    const missing = questionnaire.questions.filter((q) => answers[q.question_id] === undefined);
    if (missing.length > 0) {
      setInvalidQuestionIds(new Set(missing.map((q) => q.question_id)));
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const payload = questionnaire.questions.map((q) => {
        const answerValue = answers[q.question_id];
        if (answerValue === undefined) {
          throw new Error('unreachable: validated above');
        }
        return { question_id: q.question_id, answer_value: answerValue };
      });
      const result = await submitRiskProfile(payload);
      navigate('/customer/risk-result', { state: result });
    } catch {
      setSubmitError('The questionnaire could not be submitted. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loadError !== null) {
    return (
      <main>
        <h2>Risk-profile questionnaire</h2>
        <ErrorMessage message={loadError} />
      </main>
    );
  }

  if (questionnaire === null) {
    return (
      <main>
        <h2>Risk-profile questionnaire</h2>
        <p className="sub">Loading…</p>
      </main>
    );
  }

  const allAnswered = questionnaire.questions.every((q) => answers[q.question_id] !== undefined);

  return (
    <main className="questionnaire-page">
      <h2>Risk-profile questionnaire</h2>
      <p className="sub">
        Questions come from the active risk-band rule (version {questionnaire.rule_version}).
      </p>

      {latest !== null && (
        <div className="infobox" role="status">
          <strong>Your current band:</strong> {formatRiskBand(latest.risk_band)}. Re-submitting
          creates a new assignment; your previous one is retained.
        </div>
      )}

      {submitError !== null && <ErrorMessage message={submitError} />}

      <section className="panel">
        <form onSubmit={(event) => void handleSubmit(event)} noValidate>
          {questionnaire.questions.map((question, questionIndex) => (
            <fieldset key={question.question_id} data-invalid={invalidQuestionIds.has(question.question_id)}>
              <legend>{question.text}</legend>
              {question.options.map((option, optionIndex) => {
                const id = `${question.question_id}-${option.value}`;
                return (
                  <div className="opt" key={option.value}>
                    <input
                      type="radio"
                      id={id}
                      name={question.question_id}
                      value={option.value}
                      checked={answers[question.question_id] === option.value}
                      onChange={() => selectAnswer(question.question_id, option.value)}
                      data-testid={`question-${questionIndex + 1}-option-${optionIndex + 1}`}
                    />
                    <label htmlFor={id}>{option.label}</label>
                  </div>
                );
              })}
              {invalidQuestionIds.has(question.question_id) && (
                <p className="err" role="alert">
                  Select an answer for this question before submitting.
                </p>
              )}
            </fieldset>
          ))}
          <button type="submit" disabled={!allAnswered || isSubmitting}>
            {isSubmitting ? 'Submitting…' : 'Submit questionnaire'}
          </button>
        </form>
      </section>
    </main>
  );
}
