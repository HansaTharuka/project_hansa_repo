/**
 * Advisor customer-list, drill-in, override and manual-recommendation client
 * (E9-S3, E9-S4; api-contracts.md §11.1-§11.4). Money/percent fields are
 * fixed-point strings, forwarded/rendered verbatim or via
 * `lib/money.ts` — never `parseFloat`/`toFixed` (NFR-01).
 */
import type { RiskBand } from '../types/entities';
import { apiRequest } from './client';
import type { RecommendationResponse } from './recommendation';

export interface AdvisorCustomerSummaryResponse {
  customer_id: number;
  email: string;
  /** `null` for a customer who has never completed the questionnaire. */
  risk_band: RiskBand | null;
  kyc_verified: boolean;
  total_value: string;
  goal_count: number;
}

export interface HoldingLineResponse {
  asset_class_id: number;
  asset_class_code: string;
  current_value: string;
  current_percent: string;
  target_percent: string;
  drift_percent: string;
  exceeds_threshold: boolean;
}

export interface HoldingsResponse {
  as_of_date: string | null;
  total_value: string;
  threshold_bps: number;
  threshold_percent: string;
  holdings: HoldingLineResponse[];
}

export interface GoalResponse {
  id: number;
  customer_id: number;
  target_amount: string;
  target_date: string;
  priority: number;
  created_at: string;
  updated_at: string;
  percent_complete: string | null;
}

export interface OverrideHistoryEntryResponse {
  id: number;
  customer_id: number;
  advisor_id: number;
  previous_band: RiskBand;
  new_band: RiskBand;
  reason: string;
  note: string | null;
  created_at: string;
}

export interface AdvisorCustomerDetailResponse {
  customer_id: number;
  email: string;
  kyc_verified: boolean;
  risk_band: RiskBand | null;
  rule_version: number | null;
  holdings: HoldingsResponse;
  goals: GoalResponse[];
  /** `null` when the customer has no `RiskBandAssignment`. */
  allocation: RecommendationResponse | null;
  override_history: OverrideHistoryEntryResponse[];
}

export interface AdvisorOverrideRequest {
  new_band: RiskBand;
  /** Required, non-empty after trimming — enforced server-side (422
   * `REASON_REQUIRED`) and pre-checked client-side by `OverrideForm.tsx`. */
  reason: string;
  note?: string;
}

export interface AdvisorOverrideResponse {
  override_id: number;
  customer_id: number;
  previous_band: RiskBand;
  new_band: RiskBand;
  reason: string;
  note: string | null;
  created_at: string;
  assignment_id: number;
  risk_band: RiskBand;
}

export interface ManualRecommendationResponse {
  audit_entry_id: number;
  customer_id: number;
  advisor_id: number;
  note: string;
  created_at: string;
}

export function getAdvisorCustomers(): Promise<AdvisorCustomerSummaryResponse[]> {
  return apiRequest<AdvisorCustomerSummaryResponse[]>('/api/advisor/customers');
}

export function getAdvisorCustomerDetail(
  customerId: number
): Promise<AdvisorCustomerDetailResponse> {
  return apiRequest<AdvisorCustomerDetailResponse>(`/api/advisor/customers/${customerId}`);
}

export function overrideRiskBand(
  customerId: number,
  body: AdvisorOverrideRequest
): Promise<AdvisorOverrideResponse> {
  return apiRequest<AdvisorOverrideResponse>(`/api/advisor/customers/${customerId}/override`, {
    method: 'POST',
    body,
  });
}

/** `note` is the only body field (api-contracts.md §11.4) — `customer_id`
 * comes from the path and `advisor_id` from the JWT, so neither has a
 * client-supplied parameter here. */
export function postManualRecommendation(
  customerId: number,
  note: string
): Promise<ManualRecommendationResponse> {
  return apiRequest<ManualRecommendationResponse>(
    `/api/advisor/customers/${customerId}/manual-recommendation`,
    { method: 'POST', body: { note } }
  );
}
