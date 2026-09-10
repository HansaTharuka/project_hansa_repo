/**
 * Risk-profile questionnaire client (E4-S4; api-contracts.md §6.1-6.3).
 *
 * `points` is deliberately never present in the questionnaire response
 * (api-contracts.md §6.1 note: the client must not be able to
 * reverse-engineer or pre-compute the resulting band). The local
 * `QuestionnaireQuestion`/`QuestionnaireOption` shapes below intentionally
 * differ from `types/entities.ts`'s `Question`/`QuestionOption`, which
 * describe the server-side stored (points-included) shape instead.
 */
import type { RiskBand } from '../types/entities';
import { apiRequest, ApiError } from './client';

export interface QuestionnaireOption {
  value: string;
  label: string;
}

export interface QuestionnaireQuestion {
  question_id: string;
  text: string;
  options: QuestionnaireOption[];
}

export interface QuestionnaireResponse {
  rule_version: number;
  questions: QuestionnaireQuestion[];
}

export interface RiskBandAssignmentResponse {
  assignment_id: number;
  customer_id: number;
  risk_band: RiskBand;
  rule_version: number;
  assigned_at: string;
}

export interface SubmitAnswer {
  question_id: string;
  answer_value: string;
}

export function getQuestionnaire(): Promise<QuestionnaireResponse> {
  return apiRequest<QuestionnaireResponse>('/api/risk-profile/questionnaire');
}

/**
 * Resolves `null` (never a thrown error) when the customer has not yet been
 * assigned a band — `404 NO_RISK_BAND_ASSIGNMENT` is an expected, normal
 * response for this endpoint (api-contracts.md §6.3), not a failure.
 */
export async function getLatestRiskBandAssignment(): Promise<RiskBandAssignmentResponse | null> {
  try {
    return await apiRequest<RiskBandAssignmentResponse>('/api/risk-profile/latest');
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      return null;
    }
    throw caught;
  }
}

export function submitRiskProfile(answers: SubmitAnswer[]): Promise<RiskBandAssignmentResponse> {
  return apiRequest<RiskBandAssignmentResponse>('/api/risk-profile/submit', {
    method: 'POST',
    body: { answers },
  });
}

const RISK_BAND_LABELS: Record<RiskBand, string> = {
  CONSERVATIVE: 'Conservative',
  MODERATE: 'Moderate',
  AGGRESSIVE: 'Aggressive',
};

/** Human-readable form of a `RiskBand` enum value (E4-S4 AC2, AC5), e.g.
 * `MODERATE` -> `Moderate`. */
export function formatRiskBand(band: RiskBand): string {
  return RISK_BAND_LABELS[band];
}
