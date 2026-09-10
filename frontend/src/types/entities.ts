/**
 * TypeScript mirrors of the backend Pydantic entities (E1-S1 AC5).
 *
 * Field names are identical to `backend/src/types/entities.py` — snake_case, no key
 * mapping — so a JSON response deserialises straight into these shapes.
 *
 * Money, percentage and unit values are `string`, never `number`: a JSON number
 * becomes an IEEE-754 double in JavaScript, which is what NFR-01 forbids
 * (data-models.md §2). The two exceptions are `threshold_bps` and `percent_bps`,
 * whose canonical representation is an integer count of basis points.
 */

export type Role = 'customer' | 'advisor' | 'admin' | 'compliance';

export type RiskBand = 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';

export type RecommendationStatus = 'pending' | 'accepted' | 'dismissed';

export type TradeAction = 'BUY' | 'SELL';

export type AuditEntityType =
  | 'RiskBandAssignment'
  | 'AllocationRecommendation'
  | 'RebalancingRecommendation'
  | 'AdvisorOverride'
  | 'ManualRecommendation'
  | 'RiskBandRule'
  | 'AllocationTemplate'
  | 'AssetClass'
  | 'RebalancingThreshold';

export type AuditAction =
  | 'ASSIGN_RISK_BAND'
  | 'GENERATE_ALLOCATION_RECOMMENDATION'
  | 'GENERATE_REBALANCING_RECOMMENDATION'
  | 'ACCEPT_REBALANCING_RECOMMENDATION'
  | 'DISMISS_REBALANCING_RECOMMENDATION'
  | 'OVERRIDE_RISK_BAND'
  | 'LOG_MANUAL_RECOMMENDATION'
  | 'PUBLISH_RISK_BAND_RULE'
  | 'PUBLISH_ALLOCATION_TEMPLATE'
  | 'PUBLISH_REBALANCING_THRESHOLD'
  | 'CREATE_ASSET_CLASS'
  | 'UPDATE_ASSET_CLASS';

export type AuditDetailValue = string | number | boolean;

export interface QuestionOption {
  value: string;
  label: string;
  points: number;
}

export interface Question {
  question_id: string;
  text: string;
  options: QuestionOption[];
}

export interface Questionnaire {
  questions: Question[];
}

export interface BandRange {
  risk_band: RiskBand;
  min_points: number;
  max_points: number;
}

export interface ScoringRules {
  bands: BandRange[];
}

/** Stored form: integer basis points, summing to exactly 10000 (data-models.md §4.6). */
export interface AllocationEntry {
  asset_class_id: number;
  percent_bps: number;
}

export interface AllocationSet {
  allocations: AllocationEntry[];
}

export interface ProposedAction {
  asset_class_id: number;
  asset_class_code: string;
  action: TradeAction;
  /** Money, 2 decimals: "3200.00". */
  amount: string;
  /** Units, 4 decimals: "24.1600". */
  units: string;
  /** Signed percentage, 2 decimals: "-6.40". */
  drift_percent: string;
}

export interface ProposedActions {
  actions: ProposedAction[];
  threshold_bps: number;
  threshold_version: number;
}

export interface User {
  id: number;
  email: string;
  password_hash: string;
  role: Role;
  created_at: string;
}

export interface Customer {
  id: number;
  user_id: number;
  kyc_verified: boolean;
  created_at: string;
}

export interface RiskProfileAnswer {
  id: number;
  customer_id: number;
  question_id: string;
  answer_value: string;
  submitted_at: string;
}

export interface RiskBandAssignment {
  id: number;
  customer_id: number;
  risk_band: RiskBand;
  rule_version: number;
  assigned_at: string;
}

export interface RiskBandRule {
  id: number;
  version: number;
  questionnaire_json: Questionnaire;
  scoring_rules_json: ScoringRules;
  published_at: string;
  is_active: boolean;
}

export interface AllocationTemplate {
  id: number;
  version: number;
  risk_band: RiskBand;
  allocations_json: AllocationSet;
  published_at: string;
  is_active: boolean;
}

export interface Goal {
  id: number;
  customer_id: number;
  /** Money, 2 decimals: "250000.00". */
  target_amount: string;
  target_date: string;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface GoalProgressSnapshot {
  id: number;
  goal_id: number;
  /** Money, 2 decimals: "62500.00". */
  current_value: string;
  /** Percentage, 2 decimals, capped at "200.00". */
  percent_complete: string;
  snapshot_at: string;
  price_date: string;
}

export interface AssetClass {
  id: number;
  code: string;
  name: string;
}

export interface NavSnapshot {
  id: number;
  asset_class_id: number;
  price_date: string;
  /** Money, 2 decimals: "132.45". */
  nav_value: string;
}

export interface Holding {
  id: number;
  customer_id: number;
  asset_class_id: number;
  /** Money, 2 decimals: "48200.00". */
  current_value: string;
  as_of_date: string;
}

export interface RebalancingRecommendation {
  id: number;
  customer_id: number;
  /** Public UUID4 used in API paths. */
  recommendation_id: string;
  proposed_actions_json: ProposedActions;
  status: RecommendationStatus;
  generated_at: string;
  resolved_at: string | null;
}

export interface AdvisorOverride {
  id: number;
  customer_id: number;
  advisor_id: number;
  previous_band: RiskBand;
  new_band: RiskBand;
  reason: string;
  note: string | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  entity_type: AuditEntityType;
  entity_id: string;
  actor_id: number;
  actor_role: Role;
  action: AuditAction;
  timestamp: string;
  details_json: Record<string, AuditDetailValue>;
}

export interface RebalancingThreshold {
  id: number;
  version: number;
  /** Basis points — the documented integer exception to the string rule. */
  threshold_bps: number;
  published_at: string;
  is_active: boolean;
}
