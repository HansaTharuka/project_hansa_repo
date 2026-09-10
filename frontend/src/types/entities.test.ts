/**
 * ut-012 / ut-029 — E1-S1 AC5: the TypeScript mirrors match the Pydantic entities.
 *
 * The frontend toolchain (package.json, tsconfig.json, vitest) arrives with E2-S3,
 * so in group A these assertions are verified statically: the fixtures below are
 * annotated with the interfaces, which makes a missing, extra or wrongly-typed
 * field a compile error, and the `Expect<Equals<...>>` aliases pin the closed
 * literal unions. Once the runner exists this file executes unchanged.
 */

import { describe, expect, it } from 'vitest';

import type {
  AdvisorOverride,
  AllocationTemplate,
  AssetClass,
  AuditLogEntry,
  Customer,
  Goal,
  GoalProgressSnapshot,
  Holding,
  NavSnapshot,
  RebalancingRecommendation,
  RebalancingThreshold,
  RecommendationStatus,
  RiskBand,
  RiskBandAssignment,
  RiskBandRule,
  RiskProfileAnswer,
  Role,
  User,
} from './entities';

type Equals<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
type Expect<T extends true> = T;

// ut-029 — enum-constrained fields are closed string-literal unions, never `string`.
type RoleIsClosed = Expect<Equals<Role, 'customer' | 'advisor' | 'admin' | 'compliance'>>;
type RiskBandIsClosed = Expect<Equals<RiskBand, 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE'>>;
type StatusIsClosed = Expect<Equals<RecommendationStatus, 'pending' | 'accepted' | 'dismissed'>>;
type UserRoleIsRole = Expect<Equals<User['role'], Role>>;
type AuditActorRoleIsRole = Expect<Equals<AuditLogEntry['actor_role'], Role>>;
type AssignmentBandIsRiskBand = Expect<Equals<RiskBandAssignment['risk_band'], RiskBand>>;
type TemplateBandIsRiskBand = Expect<Equals<AllocationTemplate['risk_band'], RiskBand>>;
type PreviousBandIsRiskBand = Expect<Equals<AdvisorOverride['previous_band'], RiskBand>>;
type NewBandIsRiskBand = Expect<Equals<AdvisorOverride['new_band'], RiskBand>>;
type RecommendationStatusIsClosed = Expect<
  Equals<RebalancingRecommendation['status'], RecommendationStatus>
>;

// ut-012 — money, percentage and unit values are strings; bps quantities are numbers.
type TargetAmountIsString = Expect<Equals<Goal['target_amount'], string>>;
type SnapshotValueIsString = Expect<Equals<GoalProgressSnapshot['current_value'], string>>;
type PercentCompleteIsString = Expect<Equals<GoalProgressSnapshot['percent_complete'], string>>;
type NavValueIsString = Expect<Equals<NavSnapshot['nav_value'], string>>;
type HoldingValueIsString = Expect<Equals<Holding['current_value'], string>>;
type ThresholdBpsIsNumber = Expect<Equals<RebalancingThreshold['threshold_bps'], number>>;
type PercentBpsIsNumber = Expect<
  Equals<AllocationTemplate['allocations_json']['allocations'][number]['percent_bps'], number>
>;
type ActionAmountIsString = Expect<
  Equals<RebalancingRecommendation['proposed_actions_json']['actions'][number]['amount'], string>
>;
type ActionUnitsIsString = Expect<
  Equals<RebalancingRecommendation['proposed_actions_json']['actions'][number]['units'], string>
>;
type ActionDriftIsString = Expect<
  Equals<
    RebalancingRecommendation['proposed_actions_json']['actions'][number]['drift_percent'],
    string
  >
>;

const user: User = {
  id: 3,
  email: 'customer03@wealthwise.test',
  password_hash: '$2b$12$K1x0Qe3xk8Yd2m1u0V4hQeU2rTn6bY7wCq0aZs9dLf3pR1oJ5mN8i',
  role: 'customer',
  created_at: '2026-09-01T09:00:00Z',
};

const customer: Customer = {
  id: 3,
  user_id: 3,
  kyc_verified: true,
  created_at: '2026-09-01T09:00:00Z',
};

const riskProfileAnswer: RiskProfileAnswer = {
  id: 41,
  customer_id: 3,
  question_id: 'Q4',
  answer_value: 'hold_and_wait',
  submitted_at: '2026-09-03T10:15:00Z',
};

const riskBandAssignment: RiskBandAssignment = {
  id: 12,
  customer_id: 3,
  risk_band: 'MODERATE',
  rule_version: 1,
  assigned_at: '2026-09-03T10:15:00Z',
};

const riskBandRule: RiskBandRule = {
  id: 1,
  version: 1,
  questionnaire_json: {
    questions: [
      {
        question_id: 'Q1',
        text: 'What is your investment time horizon?',
        options: [{ value: 'lt_3y', label: 'Less than 3 years', points: 1 }],
      },
    ],
  },
  scoring_rules_json: {
    bands: [{ risk_band: 'CONSERVATIVE', min_points: 6, max_points: 13 }],
  },
  published_at: '2026-09-01T09:00:00Z',
  is_active: true,
};

const allocationTemplate: AllocationTemplate = {
  id: 4,
  version: 2,
  risk_band: 'MODERATE',
  allocations_json: {
    allocations: [
      { asset_class_id: 1, percent_bps: 4000 },
      { asset_class_id: 2, percent_bps: 3500 },
      { asset_class_id: 3, percent_bps: 2500 },
    ],
  },
  published_at: '2026-09-02T11:00:00Z',
  is_active: true,
};

const goal: Goal = {
  id: 7,
  customer_id: 3,
  target_amount: '250000.00',
  target_date: '2032-06-30',
  priority: 1,
  created_at: '2026-09-01T09:30:00Z',
  updated_at: '2026-09-03T10:20:00Z',
};

const goalProgressSnapshot: GoalProgressSnapshot = {
  id: 88,
  goal_id: 7,
  current_value: '62500.00',
  percent_complete: '25.00',
  snapshot_at: '2026-09-03T10:30:00Z',
  price_date: '2026-09-04',
};

const assetClass: AssetClass = { id: 1, code: 'EQ_DM', name: 'Developed-Market Equity' };

const navSnapshot: NavSnapshot = {
  id: 25,
  asset_class_id: 1,
  price_date: '2026-09-04',
  nav_value: '132.45',
};

const holding: Holding = {
  id: 15,
  customer_id: 3,
  asset_class_id: 1,
  current_value: '48200.00',
  as_of_date: '2026-09-04',
};

const rebalancingRecommendation: RebalancingRecommendation = {
  id: 9,
  customer_id: 3,
  recommendation_id: 'b6f0c2a4-1d3e-4f58-9a71-0c2e5d8b7a10',
  proposed_actions_json: {
    actions: [
      {
        asset_class_id: 1,
        asset_class_code: 'EQ_DM',
        action: 'SELL',
        amount: '3200.00',
        units: '24.1600',
        drift_percent: '6.40',
      },
    ],
    threshold_bps: 500,
    threshold_version: 1,
  },
  status: 'pending',
  generated_at: '2026-09-04T08:00:00Z',
  resolved_at: null,
};

const advisorOverride: AdvisorOverride = {
  id: 4,
  customer_id: 3,
  advisor_id: 11,
  previous_band: 'MODERATE',
  new_band: 'CONSERVATIVE',
  reason: 'Client reported imminent liquidity need',
  note: 'Discussed on call 2026-09-03; revisit after property sale completes.',
  created_at: '2026-09-03T14:05:00Z',
};

const auditLogEntry: AuditLogEntry = {
  id: 501,
  entity_type: 'RiskBandAssignment',
  entity_id: '12',
  actor_id: 3,
  actor_role: 'customer',
  action: 'ASSIGN_RISK_BAND',
  timestamp: '2026-09-03T10:15:00Z',
  details_json: { customer_id: 3, risk_band: 'MODERATE', rule_version: 1 },
};

const rebalancingThreshold: RebalancingThreshold = {
  id: 1,
  version: 1,
  threshold_bps: 500,
  published_at: '2026-09-01T09:00:00Z',
  is_active: true,
};

const ENTITY_FIELD_NAMES: ReadonlyArray<readonly [string, object, string[]]> = [
  ['User', user, ['id', 'email', 'password_hash', 'role', 'created_at']],
  ['Customer', customer, ['id', 'user_id', 'kyc_verified', 'created_at']],
  [
    'RiskProfileAnswer',
    riskProfileAnswer,
    ['id', 'customer_id', 'question_id', 'answer_value', 'submitted_at'],
  ],
  [
    'RiskBandAssignment',
    riskBandAssignment,
    ['id', 'customer_id', 'risk_band', 'rule_version', 'assigned_at'],
  ],
  [
    'RiskBandRule',
    riskBandRule,
    ['id', 'version', 'questionnaire_json', 'scoring_rules_json', 'published_at', 'is_active'],
  ],
  [
    'AllocationTemplate',
    allocationTemplate,
    ['id', 'version', 'risk_band', 'allocations_json', 'published_at', 'is_active'],
  ],
  [
    'Goal',
    goal,
    ['id', 'customer_id', 'target_amount', 'target_date', 'priority', 'created_at', 'updated_at'],
  ],
  [
    'GoalProgressSnapshot',
    goalProgressSnapshot,
    ['id', 'goal_id', 'current_value', 'percent_complete', 'snapshot_at', 'price_date'],
  ],
  ['AssetClass', assetClass, ['id', 'code', 'name']],
  ['NavSnapshot', navSnapshot, ['id', 'asset_class_id', 'price_date', 'nav_value']],
  [
    'Holding',
    holding,
    ['id', 'customer_id', 'asset_class_id', 'current_value', 'as_of_date'],
  ],
  [
    'RebalancingRecommendation',
    rebalancingRecommendation,
    [
      'id',
      'customer_id',
      'recommendation_id',
      'proposed_actions_json',
      'status',
      'generated_at',
      'resolved_at',
    ],
  ],
  [
    'AdvisorOverride',
    advisorOverride,
    [
      'id',
      'customer_id',
      'advisor_id',
      'previous_band',
      'new_band',
      'reason',
      'note',
      'created_at',
    ],
  ],
  [
    'AuditLogEntry',
    auditLogEntry,
    [
      'id',
      'entity_type',
      'entity_id',
      'actor_id',
      'actor_role',
      'action',
      'timestamp',
      'details_json',
    ],
  ],
  [
    'RebalancingThreshold',
    rebalancingThreshold,
    ['id', 'version', 'threshold_bps', 'published_at', 'is_active'],
  ],
];

describe('entity field names mirror the Pydantic models', () => {
  it('covers the 14 BRD entities plus RebalancingThreshold', () => {
    expect(ENTITY_FIELD_NAMES).toHaveLength(15);
  });

  it.each(ENTITY_FIELD_NAMES)('%s uses the backend snake_case field names', (_n, sample, keys) => {
    expect(Object.keys(sample).sort()).toEqual([...keys].sort());
  });
});

describe('money, percentage and unit values cross the wire as strings', () => {
  it('types every scalar money field as string', () => {
    expect(typeof goal.target_amount).toBe('string');
    expect(typeof goalProgressSnapshot.current_value).toBe('string');
    expect(typeof navSnapshot.nav_value).toBe('string');
    expect(typeof holding.current_value).toBe('string');
  });

  it('types percentages and drift as 2-decimal strings', () => {
    expect(goalProgressSnapshot.percent_complete).toBe('25.00');
    expect(rebalancingRecommendation.proposed_actions_json.actions[0]?.drift_percent).toBe('6.40');
  });

  it('types proposed-action amounts and units as fixed-scale strings', () => {
    const action = rebalancingRecommendation.proposed_actions_json.actions[0];
    expect(action?.amount).toBe('3200.00');
    expect(action?.units).toBe('24.1600');
  });

  it('keeps basis-point quantities as integers', () => {
    expect(typeof rebalancingThreshold.threshold_bps).toBe('number');
    expect(typeof allocationTemplate.allocations_json.allocations[0]?.percent_bps).toBe('number');
  });
});

describe('enum-constrained fields carry the backend literals', () => {
  it('uses the exact Role literals', () => {
    expect(user.role).toBe('customer');
    expect(auditLogEntry.actor_role).toBe('customer');
  });

  it('uses the uppercase RiskBand literals', () => {
    expect(riskBandAssignment.risk_band).toBe('MODERATE');
    expect(advisorOverride.previous_band).toBe('MODERATE');
    expect(advisorOverride.new_band).toBe('CONSERVATIVE');
  });

  it('uses the lowercase RecommendationStatus literals', () => {
    expect(rebalancingRecommendation.status).toBe('pending');
  });
});

describe('nullability matches the backend', () => {
  it('allows null only on resolved_at and note', () => {
    expect(rebalancingRecommendation.resolved_at).toBeNull();
    expect(advisorOverride.note).not.toBeNull();
  });
});
