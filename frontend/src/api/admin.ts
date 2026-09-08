/**
 * Admin console API client — risk-band rules, allocation templates,
 * asset-class master, and rebalancing thresholds (E10-S4;
 * api-contracts.md §12.2-§12.10). Every path here is `admin`-role only; the
 * shared `apiRequest` wrapper attaches the bearer token and decodes any
 * non-2xx response into `ApiError` (status, machine-readable `code`, and the
 * server's `message`) — callers never see a raw `Response` or fetch error.
 */
import type { Question, RiskBand, ScoringRules } from '../types/entities';
import { apiRequest } from './client';

export interface RiskBandRuleResponse {
  id: number;
  version: number;
  questionnaire_json: { questions: Question[] };
  scoring_rules_json: ScoringRules;
  published_at: string;
  is_active: boolean;
}

export interface PublishRiskBandRuleRequest {
  questionnaire_json: { questions: Question[] };
  scoring_rules_json: ScoringRules;
}

export interface PublishRiskBandRuleResponse {
  id: number;
  version: number;
  published_at: string;
  is_active: boolean;
}

/** GET /api/admin/risk-band-rules — every version, active and superseded. */
export function getRiskBandRules(): Promise<RiskBandRuleResponse[]> {
  return apiRequest<RiskBandRuleResponse[]>('/api/admin/risk-band-rules');
}

/** POST /api/admin/risk-band-rules — publishes the next version. */
export function publishRiskBandRule(
  payload: PublishRiskBandRuleRequest,
): Promise<PublishRiskBandRuleResponse> {
  return apiRequest<PublishRiskBandRuleResponse>('/api/admin/risk-band-rules', {
    method: 'POST',
    body: payload,
  });
}

export interface AllocationRequestEntry {
  asset_class_id: number;
  /** 2-decimal-place percent string, e.g. "40.00" (NFR-01) — never a number. */
  percent: string;
}

export interface AllocationTemplateResponse {
  id: number;
  version: number;
  risk_band: RiskBand;
  allocations: Array<AllocationRequestEntry & { asset_class_code: string }>;
  total_percent: string;
  published_at: string;
  is_active: boolean;
}

export interface PublishAllocationTemplateRequest {
  risk_band: RiskBand;
  allocations: AllocationRequestEntry[];
}

export interface PublishAllocationTemplateResponse {
  id: number;
  version: number;
  risk_band: RiskBand;
  total_percent: string;
  published_at: string;
  is_active: boolean;
}

/** GET /api/admin/allocation-templates[?risk_band=...] — every version for
 * the band(s), active and superseded. */
export function getAllocationTemplates(riskBand?: RiskBand): Promise<AllocationTemplateResponse[]> {
  const path =
    riskBand !== undefined
      ? `/api/admin/allocation-templates?risk_band=${riskBand}`
      : '/api/admin/allocation-templates';
  return apiRequest<AllocationTemplateResponse[]>(path);
}

/** POST /api/admin/allocation-templates — publishes the next version for
 * `payload.risk_band`. The server re-validates the sum-to-10000-bps rule
 * (TEMPLATE_SUM_INVALID); the UI's own gate in lib/money.ts must never be
 * the only thing standing between an invalid sum and this call. */
export function publishAllocationTemplate(
  payload: PublishAllocationTemplateRequest,
): Promise<PublishAllocationTemplateResponse> {
  return apiRequest<PublishAllocationTemplateResponse>('/api/admin/allocation-templates', {
    method: 'POST',
    body: payload,
  });
}

export interface AssetClassResponse {
  id: number;
  code: string;
  name: string;
}

export interface CreateAssetClassRequest {
  code: string;
  name: string;
}

/** GET /api/admin/asset-classes — the full master list, ordered by code. */
export function getAssetClasses(): Promise<AssetClassResponse[]> {
  return apiRequest<AssetClassResponse[]>('/api/admin/asset-classes');
}

/** POST /api/admin/asset-classes — a duplicate `code` rejects with 409
 * DUPLICATE_ASSET_CLASS_CODE; callers surface `ApiError.message` inline
 * rather than a generic error (E10-S4 AC4). */
export function createAssetClass(payload: CreateAssetClassRequest): Promise<AssetClassResponse> {
  return apiRequest<AssetClassResponse>('/api/admin/asset-classes', {
    method: 'POST',
    body: payload,
  });
}

export interface RebalancingThresholdResponse {
  id: number;
  version: number;
  /** Basis points — the documented integer exception to the string rule. */
  threshold_bps: number;
  /** 2-decimal-place percent string derived from `threshold_bps`. */
  threshold_percent: string;
  published_at: string;
  is_active: boolean;
}

export interface PublishRebalancingThresholdRequest {
  threshold_bps: number;
}

/** GET /api/admin/rebalancing-thresholds — every version, ordered by version. */
export function getRebalancingThresholds(): Promise<RebalancingThresholdResponse[]> {
  return apiRequest<RebalancingThresholdResponse[]>('/api/admin/rebalancing-thresholds');
}

/** POST /api/admin/rebalancing-thresholds — publishes the next version. */
export function publishRebalancingThreshold(
  payload: PublishRebalancingThresholdRequest,
): Promise<RebalancingThresholdResponse> {
  return apiRequest<RebalancingThresholdResponse>('/api/admin/rebalancing-thresholds', {
    method: 'POST',
    body: payload,
  });
}
