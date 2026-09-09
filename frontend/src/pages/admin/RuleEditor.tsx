/**
 * Admin risk-band rule editor (E10-S4 AC3, AC5; api-contracts.md
 * §12.2/12.3). Loads the latest published RiskBandRule as the starting
 * draft, lets the admin add/remove question rows, and requires at least 6
 * questions before Publish is enabled — the same MIN_QUESTIONNAIRE_QUESTIONS
 * gate the backend re-asserts (backend/src/domain/admin/service.py).
 *
 * Each option's `points` are fixed on a 1-4 Likert scale when a question is
 * added — this screen's tested surface (AC3) is question count and text,
 * not per-option point tuning, which E10-S3's already-published defaults
 * cover well enough for a first cut.
 */
import { useEffect, useState } from 'react';

import type { PublishRiskBandRuleRequest, RiskBandRuleResponse } from '../../api/admin';
import { getRiskBandRules, publishRiskBandRule } from '../../api/admin';
import { ErrorMessage } from '../../components/ErrorMessage';
import type { Question, ScoringRules } from '../../types/entities';

const MIN_QUESTIONS = 6;

interface HistoryRow {
  id: number;
  version: number;
  questionCount: number;
  publishedAt: string;
  isActive: boolean;
}

function defaultOptions(): Question['options'] {
  return [
    { value: 'opt_1', label: 'Option 1', points: 1 },
    { value: 'opt_2', label: 'Option 2', points: 2 },
    { value: 'opt_3', label: 'Option 3', points: 3 },
    { value: 'opt_4', label: 'Option 4', points: 4 },
  ];
}

function computeScoringBands(questionCount: number): ScoringRules {
  const minTotal = questionCount * 1;
  const maxTotal = questionCount * 4;
  const span = maxTotal - minTotal + 1;
  const third = Math.max(1, Math.floor(span / 3));
  const conservativeMax = minTotal + third - 1;
  const moderateMax = minTotal + 2 * third - 1;
  return {
    bands: [
      { risk_band: 'CONSERVATIVE', min_points: minTotal, max_points: conservativeMax },
      { risk_band: 'MODERATE', min_points: conservativeMax + 1, max_points: moderateMax },
      { risk_band: 'AGGRESSIVE', min_points: moderateMax + 1, max_points: maxTotal },
    ],
  };
}

function toHistoryRow(rule: RiskBandRuleResponse): HistoryRow {
  return {
    id: rule.id,
    version: rule.version,
    questionCount: rule.questionnaire_json.questions.length,
    publishedAt: rule.published_at,
    isActive: rule.is_active,
  };
}

export function RuleEditor() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [publishedMessage, setPublishedMessage] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getRiskBandRules()
      .then((rules) => {
        if (cancelled) {
          return;
        }
        setHistory(rules.map(toHistoryRow));
        const latest = rules.at(-1);
        setQuestions(latest?.questionnaire_json.questions ?? []);
      })
      .catch(() => {
        if (!cancelled) {
          setError('Risk-band rules could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function addQuestion(): void {
    const nextId = `Q${questions.length + 1}`;
    setQuestions((current) => [...current, { question_id: nextId, text: '', options: defaultOptions() }]);
  }

  function removeQuestion(index: number): void {
    setQuestions((current) => current.filter((_, i) => i !== index));
  }

  function updateQuestionText(index: number, text: string): void {
    setQuestions((current) => current.map((question, i) => (i === index ? { ...question, text } : question)));
  }

  const canPublish = questions.length >= MIN_QUESTIONS;

  async function handlePublish(): Promise<void> {
    if (!canPublish) {
      return;
    }
    setError(null);
    setIsPublishing(true);
    const payload: PublishRiskBandRuleRequest = {
      questionnaire_json: { questions },
      scoring_rules_json: computeScoringBands(questions.length),
    };
    try {
      const response = await publishRiskBandRule(payload);
      setPublishedMessage(`Published version ${response.version}.`);
      setHistory((current) => [
        ...current,
        {
          id: response.id,
          version: response.version,
          questionCount: questions.length,
          publishedAt: response.published_at,
          isActive: response.is_active,
        },
      ]);
    } catch {
      setError('Publish failed. Please try again.');
    } finally {
      setIsPublishing(false);
    }
  }

  return (
    <main className="admin-page">
      <h2>Risk-band rule editor</h2>
      <p className="sub">Questionnaire &amp; scoring rules — at least {MIN_QUESTIONS} questions are required to publish.</p>

      {error !== null && <ErrorMessage message={error} />}
      {publishedMessage !== null && (
        <div className="okbox" role="status">
          {publishedMessage}
        </div>
      )}

      <section className="panel">
        <p className={`count-note${canPublish ? '' : ' bad'}`}>
          {questions.length} {questions.length === 1 ? 'question' : 'questions'} defined — at least{' '}
          {MIN_QUESTIONS} are required to publish.
        </p>

        {questions.map((question, index) => (
          <QuestionRow
            key={question.question_id}
            question={question}
            index={index}
            onTextChange={(text) => updateQuestionText(index, text)}
            onRemove={() => removeQuestion(index)}
          />
        ))}

        <p>
          <button type="button" className="secondary small" data-testid="add-question" onClick={addQuestion}>
            Add question
          </button>
        </p>

        <button
          type="button"
          data-testid="rule-publish"
          disabled={!canPublish || isPublishing}
          onClick={() => void handlePublish()}
        >
          {isPublishing ? 'Publishing…' : 'Publish new version'}
        </button>
      </section>

      <section className="panel">
        <h3>Version history</h3>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th scope="col">id</th>
                <th scope="col" className="num">
                  version
                </th>
                <th scope="col" className="num">
                  question count
                </th>
                <th scope="col">published_at</th>
                <th scope="col">is_active</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td className="num">{row.version}</td>
                  <td className="num">{row.questionCount}</td>
                  <td>{row.publishedAt}</td>
                  <td>{String(row.isActive)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

interface QuestionRowProps {
  question: Question;
  index: number;
  onTextChange: (text: string) => void;
  onRemove: () => void;
}

function QuestionRow({ question, index, onTextChange, onRemove }: QuestionRowProps) {
  const textInputId = `question-${index}-text`;
  return (
    <div className="question">
      <div className="qhead">
        <span className="qid">{question.question_id}</span>
        <button
          type="button"
          className="secondary small"
          onClick={onRemove}
          aria-label={`Remove question ${question.question_id}`}
        >
          Remove
        </button>
      </div>
      <label htmlFor={textInputId}>Question text for {question.question_id}</label>
      <input
        id={textInputId}
        type="text"
        value={question.text}
        onChange={(event) => onTextChange(event.target.value)}
      />
    </div>
  );
}
