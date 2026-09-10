"""GET /api/advisor/customers, GET /api/advisor/customers/{customer_id},
POST .../override, POST .../manual-recommendation — advisor-role customer
list, drill-in, override and manual-recommendation logging (E9-S3 AC1-AC5;
api-contracts.md §11.1-§11.4).

This router calls `domain.advisor.service` exclusively — never a repository
or `db.models` directly (system-design.md D3), and never raises
`HTTPException` itself. All four routes require the `advisor` role; a
customer- or compliance-role token is rejected with 403 by the shared
`require_role` dependency before any handler body runs (AC5).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, get_settings, require_role
from src.core.config import Settings
from src.domain.advisor.service import (
    CustomerDetail,
    CustomerSummary,
    OverrideResult,
    get_customer_detail,
    list_customers,
    log_manual_recommendation,
    override_risk_band,
)
from src.domain.holdings.views import CustomerHoldingsView, HoldingLine
from src.domain.recommendation.service import AllocationLine, RecommendationResult
from src.types.entities import AdvisorOverride, Goal
from src.types.fixedpoint import (
    decimal_to_basis_points,
    decimal_to_minor_units,
    money_to_string,
    percent_to_string,
)
from src.types.requests import AdvisorOverrideRequest, ManualRecommendationRequest
from src.types.responses import (
    AdvisorCustomerDetailResponse,
    AdvisorCustomerSummaryResponse,
    AdvisorOverrideResponse,
    AllocationEntryResponse,
    GoalResponse,
    HoldingLineResponse,
    HoldingsResponse,
    ManualRecommendationResponse,
    OverrideHistoryEntryResponse,
    RecommendationResponse,
)

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.get("/customers", status_code=200)
def get_customers(
    user: CurrentUser = Depends(require_role("advisor")),
    session: Session = Depends(get_session, scope="function"),
) -> list[AdvisorCustomerSummaryResponse]:
    """Every customer with their current risk band (AC1)."""
    del user
    return [_summary_to_response(summary) for summary in list_customers(session)]


@router.get("/customers/{customer_id}", status_code=200)
def get_customer_drill_in(
    customer_id: int,
    user: CurrentUser = Depends(require_role("advisor")),
    session: Session = Depends(get_session, scope="function"),
    settings: Settings = Depends(get_settings),
) -> AdvisorCustomerDetailResponse:
    """Full portfolio detail for one customer in a single call (AC2). An
    unknown `customer_id` raises `NotFoundError` (`CUSTOMER_NOT_FOUND`).
    """
    del user
    default_threshold_bps = settings.default_drift_threshold_percent * 100
    detail = get_customer_detail(
        session, customer_id, default_threshold_bps=default_threshold_bps
    )
    return _detail_to_response(detail)


@router.post("/customers/{customer_id}/override", status_code=201)
def post_override(
    customer_id: int,
    body: AdvisorOverrideRequest,
    user: CurrentUser = Depends(require_role("advisor")),
    session: Session = Depends(get_session, scope="function"),
) -> AdvisorOverrideResponse:
    """Override `customer_id`'s risk band with a mandatory reason (AC3). A
    missing/blank `reason` raises `ValidationError` (`REASON_REQUIRED`)
    before any row is written.
    """
    result = override_risk_band(
        session,
        customer_id=customer_id,
        advisor_id=user.user_id,
        new_band=body.new_band,
        reason=body.reason,
        note=body.note,
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return _override_to_response(result)


@router.post("/customers/{customer_id}/manual-recommendation", status_code=201)
def post_manual_recommendation(
    customer_id: int,
    body: ManualRecommendationRequest,
    user: CurrentUser = Depends(require_role("advisor")),
    session: Session = Depends(get_session, scope="function"),
) -> ManualRecommendationResponse:
    """Log a manual recommendation as an audit-only event (AC4) — no new
    table is written, only one `AuditLogEntry`.
    """
    result = log_manual_recommendation(
        session,
        customer_id=customer_id,
        advisor_id=user.user_id,
        note=body.note,
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return ManualRecommendationResponse(
        audit_entry_id=result.audit_entry_id,
        customer_id=result.customer_id,
        advisor_id=result.advisor_id,
        note=result.note,
        created_at=result.created_at,
    )


def _summary_to_response(summary: CustomerSummary) -> AdvisorCustomerSummaryResponse:
    return AdvisorCustomerSummaryResponse(
        customer_id=summary.customer_id,
        email=summary.email,
        risk_band=summary.risk_band,
        kyc_verified=summary.kyc_verified,
        total_value=money_to_string(decimal_to_minor_units(summary.total_value)),
        goal_count=summary.goal_count,
    )


def _detail_to_response(detail: CustomerDetail) -> AdvisorCustomerDetailResponse:
    return AdvisorCustomerDetailResponse(
        customer_id=detail.customer_id,
        email=detail.email,
        kyc_verified=detail.kyc_verified,
        risk_band=detail.risk_band,
        rule_version=detail.rule_version,
        holdings=_holdings_to_response(detail.holdings),
        goals=[_goal_to_response(goal, percent) for goal, percent in detail.goals],
        allocation=(
            _allocation_to_response(detail.allocation) if detail.allocation is not None else None
        ),
        override_history=[
            _override_history_to_response(entry) for entry in detail.override_history
        ],
    )


def _holdings_to_response(view: CustomerHoldingsView) -> HoldingsResponse:
    return HoldingsResponse(
        as_of_date=view.as_of_date,
        total_value=money_to_string(decimal_to_minor_units(view.total_value)),
        threshold_bps=view.threshold_bps,
        threshold_percent=percent_to_string(view.threshold_bps),
        holdings=[_holding_line_to_response(line) for line in view.holdings],
    )


def _holding_line_to_response(line: HoldingLine) -> HoldingLineResponse:
    return HoldingLineResponse(
        asset_class_id=line.asset_class_id,
        asset_class_code=line.asset_class_code,
        current_value=money_to_string(decimal_to_minor_units(line.current_value)),
        current_percent=percent_to_string(decimal_to_basis_points(line.current_percent)),
        target_percent=percent_to_string(decimal_to_basis_points(line.target_percent)),
        drift_percent=percent_to_string(decimal_to_basis_points(line.drift_percent)),
        exceeds_threshold=line.exceeds_threshold,
    )


def _goal_to_response(goal: Goal, percent_complete: Decimal | None) -> GoalResponse:
    return GoalResponse(
        id=goal.id,
        customer_id=goal.customer_id,
        target_amount=str(goal.target_amount),
        target_date=goal.target_date,
        priority=goal.priority,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
        percent_complete=str(percent_complete) if percent_complete is not None else None,
    )


def _allocation_to_response(result: RecommendationResult) -> RecommendationResponse:
    total_bps = sum(decimal_to_basis_points(line.percent) for line in result.allocations)
    return RecommendationResponse(
        risk_band=result.risk_band,
        rule_version=result.rule_version,
        template_version=result.template_version,
        horizon=result.horizon,
        allocations=[_allocation_line_to_response(line) for line in result.allocations],
        total_percent=percent_to_string(total_bps),
        generated_at=result.generated_at,
    )


def _allocation_line_to_response(line: AllocationLine) -> AllocationEntryResponse:
    return AllocationEntryResponse(
        asset_class_id=line.asset_class_id,
        asset_class_code=line.asset_class_code,
        asset_class_name=line.asset_class_name,
        percent=percent_to_string(decimal_to_basis_points(line.percent)),
    )


def _override_to_response(result: OverrideResult) -> AdvisorOverrideResponse:
    return AdvisorOverrideResponse(
        override_id=result.override_id,
        customer_id=result.customer_id,
        previous_band=result.previous_band,
        new_band=result.new_band,
        reason=result.reason,
        note=result.note,
        created_at=result.created_at,
        assignment_id=result.assignment_id,
        risk_band=result.risk_band,
    )


def _override_history_to_response(override: AdvisorOverride) -> OverrideHistoryEntryResponse:
    return OverrideHistoryEntryResponse(
        id=override.id,
        customer_id=override.customer_id,
        advisor_id=override.advisor_id,
        previous_band=override.previous_band,
        new_band=override.new_band,
        reason=override.reason,
        note=override.note,
        created_at=override.created_at,
    )
