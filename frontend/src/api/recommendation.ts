/**
 * Customer recommended-allocation client (E5-S3, E5-S4; api-contracts.md
 * §7.1). `percent`/`total_percent` are fixed-point 2-decimal strings —
 * callers format/sum them through `lib/money.ts`'s basis-point helpers,
 * never `parseFloat`/`toFixed` (NFR-01).
 */
import type { RiskBand } from '../types/entities';
import { apiRequest } from './client';

export interface AllocationEntryResponse {
  asset_class_id: number;
  asset_class_code: string;
  asset_class_name: string;
  /** Percent, 2 decimals, verbatim from the API. */
  percent: string;
}

export interface RecommendationResponse {
  risk_band: RiskBand;
  rule_version: number;
  template_version: number;
  horizon: string;
  allocations: AllocationEntryResponse[];
  /** Always exactly "100.00" (AC-02) — the allocation view computes and
   * displays its own total from `allocations` rather than echoing this
   * field verbatim (E5-S4 AC1). */
  total_percent: string;
  generated_at: string;
}

export function getRecommendation(): Promise<RecommendationResponse> {
  return apiRequest<RecommendationResponse>('/api/recommendation');
}
