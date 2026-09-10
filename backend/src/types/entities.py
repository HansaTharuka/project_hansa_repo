"""Pydantic mirrors of the 14 BRD §9 entities plus `RebalancingThreshold`.

These models carry the persistence shape from data-models.md §4: field names are
the BRD's, snake_case and unchanged; timestamps and dates are ISO-8601 / YYYY-MM-DD
strings because SQLite stores them as TEXT; money and percentage values are
`Decimal`, never float (NFR-01). `User.password_hash` is present because the table
has it — the never-serialise rule is enforced by `types/responses.py`, not by
omitting the column here.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.types.enums import (
    AuditAction,
    AuditEntityType,
    RecommendationStatus,
    RiskBand,
    Role,
    TradeAction,
)

AuditDetailValue = str | int | bool


class Entity(BaseModel):
    """Base for the persistence mirrors: closed shape, immutable once built."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class QuestionOption(Entity):
    """One selectable answer inside a questionnaire question."""

    value: str
    label: str
    points: int


class Question(Entity):
    """One question of `RiskBandRule.questionnaire_json`."""

    question_id: str
    text: str
    options: list[QuestionOption]


class Questionnaire(Entity):
    """The `questionnaire_json` document (data-models.md §4.5)."""

    questions: list[Question]


class BandRange(Entity):
    """One closed, integer point range mapping a score to a risk band."""

    risk_band: RiskBand
    min_points: int
    max_points: int


class ScoringRules(Entity):
    """The `scoring_rules_json` document — contiguous, non-overlapping ranges."""

    bands: list[BandRange]


class AllocationEntry(Entity):
    """One asset-class weight in stored form: integer basis points summing to 10000."""

    asset_class_id: int
    percent_bps: int


class AllocationSet(Entity):
    """The `allocations_json` document (data-models.md §4.6)."""

    allocations: list[AllocationEntry]


class ProposedAction(Entity):
    """One BUY/SELL leg of a rebalancing proposal; `drift_percent` may be negative."""

    asset_class_id: int
    asset_class_code: str
    action: TradeAction
    amount: Decimal
    units: Decimal
    drift_percent: Decimal


class ProposedActions(Entity):
    """The `proposed_actions_json` document, with the threshold it was judged against."""

    actions: list[ProposedAction]
    threshold_bps: int
    threshold_version: int


class User(Entity):
    """data-models.md §4.1."""

    id: int
    email: str
    password_hash: str
    role: Role
    created_at: str


class Customer(Entity):
    """data-models.md §4.2."""

    id: int
    user_id: int
    kyc_verified: bool
    created_at: str


class RiskProfileAnswer(Entity):
    """data-models.md §4.3 — append-only."""

    id: int
    customer_id: int
    question_id: str
    answer_value: str
    submitted_at: str


class RiskBandAssignment(Entity):
    """data-models.md §4.4 — append-only; `rule_version` pins the rule used."""

    id: int
    customer_id: int
    risk_band: RiskBand
    rule_version: int
    assigned_at: str


class RiskBandRule(Entity):
    """data-models.md §4.5 — insert-only, immutable once published."""

    id: int
    version: int
    questionnaire_json: Questionnaire
    scoring_rules_json: ScoringRules
    published_at: str
    is_active: bool


class AllocationTemplate(Entity):
    """data-models.md §4.6 — insert-only, immutable once published."""

    id: int
    version: int
    risk_band: RiskBand
    allocations_json: AllocationSet
    published_at: str
    is_active: bool


class Goal(Entity):
    """data-models.md §4.7 — `target_amount` is money, `target_date` a YYYY-MM-DD string."""

    id: int
    customer_id: int
    target_amount: Decimal
    target_date: str
    priority: int
    created_at: str
    updated_at: str


class GoalProgressSnapshot(Entity):
    """data-models.md §4.8 — append-only; `percent_complete` caps at 200.00."""

    id: int
    goal_id: int
    current_value: Decimal
    percent_complete: Decimal
    snapshot_at: str
    price_date: str


class AssetClass(Entity):
    """data-models.md §4.9 — master data with a unique `code`."""

    id: int
    code: str
    name: str


class NavSnapshot(Entity):
    """data-models.md §4.10 — append-only price per asset class per simulated date."""

    id: int
    asset_class_id: int
    price_date: str
    nav_value: Decimal


class Holding(Entity):
    """data-models.md §4.11 — a current position, revalued on each advance-a-day."""

    id: int
    customer_id: int
    asset_class_id: int
    current_value: Decimal
    as_of_date: str


class RebalancingRecommendation(Entity):
    """data-models.md §4.12 — `recommendation_id` is the public UUID used in API paths."""

    id: int
    customer_id: int
    recommendation_id: str
    proposed_actions_json: ProposedActions
    status: RecommendationStatus
    generated_at: str
    resolved_at: str | None = None


class AdvisorOverride(Entity):
    """data-models.md §4.13 — append-only; `reason` mandatory, `note` optional."""

    id: int
    customer_id: int
    advisor_id: int
    previous_band: RiskBand
    new_band: RiskBand
    reason: str
    note: str | None = None
    created_at: str


class AuditLogEntry(Entity):
    """data-models.md §4.14 — insert-only; `details_json` carries ids and enums only."""

    id: int
    entity_type: AuditEntityType
    entity_id: str
    actor_id: int
    actor_role: Role
    action: AuditAction
    timestamp: str
    details_json: dict[str, AuditDetailValue]


class RebalancingThreshold(Entity):
    """data-models.md §4.15 — the one percent-class quantity typed `int` (basis points)."""

    id: int
    version: int
    threshold_bps: int
    published_at: str
    is_active: bool
