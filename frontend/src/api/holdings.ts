/**
 * GET /api/holdings — customer-role current holdings and per-asset-class
 * drift (E6-S5; api-contracts.md §8.1).
 */
import { apiRequest } from './client';

export interface HoldingLineResponse {
  asset_class_id: number;
  asset_class_code: string;
  /** Money, 2 decimals, verbatim from the API — never re-formatted (NFR-01). */
  current_value: string;
  /** Percent, 2 decimals, verbatim from the API. */
  current_percent: string;
  /** Percent, 2 decimals, verbatim from the API. */
  target_percent: string;
  /** Signed percent, 2 decimals, verbatim from the API. */
  drift_percent: string;
  exceeds_threshold: boolean;
}

export interface HoldingsResponse {
  as_of_date: string | null;
  /** Money, 2 decimals, verbatim from the API. */
  total_value: string;
  threshold_bps: number;
  /** Percent, 2 decimals, verbatim from the API. */
  threshold_percent: string;
  holdings: HoldingLineResponse[];
}

export function getHoldings(): Promise<HoldingsResponse> {
  return apiRequest<HoldingsResponse>('/api/holdings');
}
