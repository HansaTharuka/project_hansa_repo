"""Pydantic response models shared by the recommendation and advisor routers
(E5-S3, E9-S3; api-contracts.md §7.1, §8.1, §9.1, §11.1-§11.4).

Types layer (`.claude/architecture.md`): these are pure serialization shapes
built by routers from domain dataclasses/entities — this module imports
nothing beyond `pydantic` itself, so it may safely be imported from any
higher layer.
"""

from __future__ import annotations

from pydantic import BaseModel


class AllocationEntryResponse(BaseModel):
    """One asset class's recommended weight (api-contracts.md §7.1)."""

    asset_class_id: int
    asset_class_code: str
    asset_class_name: str
    percent: str


class RecommendationResponse(BaseModel):
    """A customer's recommended allocation (api-contracts.md §7.1)."""

    risk_band: str
    rule_version: int
    template_version: int
    horizon: str
    allocations: list[AllocationEntryResponse]
    total_percent: str
    generated_at: str


class AdvisorCustomerSummaryResponse(BaseModel):
    """One row of the advisor customer list (api-contracts.md §11.1)."""

    customer_id: int
    email: str
    risk_band: str | None
    kyc_verified: bool
    total_value: str
    goal_count: int


class HoldingLineResponse(BaseModel):
    """One asset class's current value and drift (api-contracts.md §8.1,
    reused by the advisor drill-in, §11.2)."""

    asset_class_id: int
    asset_class_code: str
    current_value: str
    current_percent: str
    target_percent: str
    drift_percent: str
    exceeds_threshold: bool


class HoldingsResponse(BaseModel):
    """A customer's full holdings-and-drift snapshot (api-contracts.md §8.1)."""

    as_of_date: str | None
    total_value: str
    threshold_bps: int
    threshold_percent: str
    holdings: list[HoldingLineResponse]


class GoalResponse(BaseModel):
    """One goal (api-contracts.md §9.1, reused by the advisor drill-in, §11.2)."""

    id: int
    customer_id: int
    target_amount: str
    target_date: str
    priority: int
    created_at: str
    updated_at: str
    percent_complete: str | None


class OverrideHistoryEntryResponse(BaseModel):
    """One `AdvisorOverride` row (api-contracts.md §11.2)."""

    id: int
    customer_id: int
    advisor_id: int
    previous_band: str
    new_band: str
    reason: str
    note: str | None
    created_at: str


class AdvisorCustomerDetailResponse(BaseModel):
    """The advisor drill-in payload — holdings, goals, allocation and override
    history in one call (api-contracts.md §11.2)."""

    customer_id: int
    email: str
    kyc_verified: bool
    risk_band: str | None
    rule_version: int | None
    holdings: HoldingsResponse
    goals: list[GoalResponse]
    allocation: RecommendationResponse | None
    override_history: list[OverrideHistoryEntryResponse]


class AdvisorOverrideResponse(BaseModel):
    """The override + new-assignment outcome (api-contracts.md §11.3)."""

    override_id: int
    customer_id: int
    previous_band: str
    new_band: str
    reason: str
    note: str | None
    created_at: str
    assignment_id: int
    risk_band: str


class ManualRecommendationResponse(BaseModel):
    """The audit-only outcome of logging a manual recommendation
    (api-contracts.md §11.4)."""

    audit_entry_id: int
    customer_id: int
    advisor_id: int
    note: str
    created_at: str
