"""POST /api/admin/advance-day — admin-role-only manual price-feed trigger
(E6-S4 AC2-AC4; api-contracts.md §12.1). E10-S3 (group F) extends this same
router with rule/template/asset-class publish routes (component-map.md note 3).

The three new POST routes translate `domain.admin.service`'s already-tested
`ValidationError`/`ConflictError` gates (E10-S2, group E) to their documented
status codes — this router never re-implements the sum/length checks
themselves, only the request/response shape around them (api-contracts.md
§12.3, §12.5, §12.7).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.admin.service import (
    create_asset_class_with_audit,
    list_allocation_templates_for_admin,
    publish_allocation_template,
    publish_risk_band_rule,
)
from src.domain.holdings.service import advance_day
from src.types.entities import AllocationEntry, AllocationSet, Questionnaire, ScoringRules
from src.types.entities import AllocationTemplate as AllocationTemplateEntity
from src.types.errors import ValidationError
from src.types.fixedpoint import percent_to_string, string_to_basis_points

router = APIRouter(prefix="/api/admin", tags=["admin"])

PERCENT_SCALE = Decimal("0.01")


class AdvanceDayResponse(BaseModel):
    """The shared response shape E6-S4/E7-S3/E8-S2 all contribute a count to."""

    price_date: str
    nav_snapshots_created: int
    holdings_revalued: int
    goal_snapshots_created: int
    rebalancing_recommendations_created: int


class RiskBandRulePublishRequest(BaseModel):
    """api-contracts.md §12.3 — `version` is server-assigned, never accepted here."""

    questionnaire_json: Questionnaire
    scoring_rules_json: ScoringRules


class RiskBandRulePublishResponse(BaseModel):
    id: int
    version: int
    published_at: str
    is_active: bool


class AllocationEntryRequest(BaseModel):
    asset_class_id: int
    percent: str = Field(min_length=1)


class AllocationTemplatePublishRequest(BaseModel):
    """api-contracts.md §12.5."""

    risk_band: str
    allocations: list[AllocationEntryRequest]


class AllocationTemplatePublishResponse(BaseModel):
    id: int
    version: int
    risk_band: str
    total_percent: str
    published_at: str
    is_active: bool


class AllocationTemplateListEntryResponse(BaseModel):
    id: int
    version: int
    risk_band: str
    allocations: list[AllocationEntryRequest]
    total_percent: str
    published_at: str
    is_active: bool


class AssetClassCreateRequest(BaseModel):
    """api-contracts.md §12.7."""

    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=100)


class AssetClassResponse(BaseModel):
    id: int
    code: str
    name: str


@router.post("/advance-day", status_code=200)
def post_advance_day(
    user: CurrentUser = Depends(require_role("admin")),
    session: Session = Depends(get_session),
) -> AdvanceDayResponse:
    """Advance the simulated price feed by exactly one day (AC2, AC3).

    A second immediate call for the same simulated day raises `ConflictError`
    (`DAY_ALREADY_ADVANCED`), mapped to 409 by the already-registered generic
    handler (AC4) — this router never constructs a status code itself.
    """
    result = advance_day(session, actor_id=user.user_id, actor_role=user.role)
    return AdvanceDayResponse(
        price_date=result.price_date,
        nav_snapshots_created=len(result.snapshots),
        holdings_revalued=result.holdings_revalued,
        goal_snapshots_created=result.goal_snapshots_created,
        rebalancing_recommendations_created=result.rebalancing_recommendations_created,
    )


@router.post("/risk-band-rules", status_code=201)
def post_risk_band_rule(
    body: RiskBandRulePublishRequest,
    user: CurrentUser = Depends(require_role("admin")),
    session: Session = Depends(get_session),
) -> RiskBandRulePublishResponse:
    """Publish the next `RiskBandRule` version (E10-S3 AC1). Fewer than 6
    questions raises `ValidationError` (`QUESTIONNAIRE_TOO_SHORT`, 422)."""
    rule = publish_risk_band_rule(
        session,
        questionnaire=body.questionnaire_json,
        scoring_rules=body.scoring_rules_json,
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return RiskBandRulePublishResponse(
        id=rule.id, version=rule.version, published_at=rule.published_at, is_active=rule.is_active
    )


@router.post("/allocation-templates", status_code=201)
def post_allocation_template(
    body: AllocationTemplatePublishRequest,
    user: CurrentUser = Depends(require_role("admin")),
    session: Session = Depends(get_session),
) -> AllocationTemplatePublishResponse:
    """Publish the next `AllocationTemplate` version for `body.risk_band`
    (E10-S3 AC2). Percentages not summing to exactly 100 raise
    `ValidationError` (`TEMPLATE_SUM_INVALID`, 422); nothing is written."""
    allocations = AllocationSet(
        allocations=[
            AllocationEntry(
                asset_class_id=entry.asset_class_id,
                percent_bps=_parse_percent_bps(entry.percent),
            )
            for entry in body.allocations
        ]
    )
    template = publish_allocation_template(
        session,
        risk_band=body.risk_band,
        allocations=allocations,
        actor_id=user.user_id,
        actor_role=user.role,
    )
    total_bps = sum(entry.percent_bps for entry in template.allocations_json.allocations)
    return AllocationTemplatePublishResponse(
        id=template.id,
        version=template.version,
        risk_band=template.risk_band,
        total_percent=_bps_to_percent_string(total_bps),
        published_at=template.published_at,
        is_active=template.is_active,
    )


@router.get("/allocation-templates", status_code=200)
def get_allocation_templates(
    risk_band: str | None = Query(default=None),
    user: CurrentUser = Depends(require_role("admin")),
    session: Session = Depends(get_session),
) -> list[AllocationTemplateListEntryResponse]:
    """Every version — active and superseded — optionally scoped to one
    `risk_band` (E10-S3 AC5)."""
    templates = list_allocation_templates_for_admin(session, risk_band=risk_band)
    return [_template_to_list_response(template) for template in templates]


@router.post("/asset-classes", status_code=201)
def post_asset_class(
    body: AssetClassCreateRequest,
    user: CurrentUser = Depends(require_role("admin")),
    session: Session = Depends(get_session),
) -> AssetClassResponse:
    """Create one `AssetClass` (E10-S3 AC3). A duplicate `code` raises
    `ConflictError` (`DUPLICATE_ASSET_CLASS_CODE`, 409)."""
    asset_class = create_asset_class_with_audit(
        session, code=body.code, name=body.name, actor_id=user.user_id, actor_role=user.role
    )
    return AssetClassResponse(id=asset_class.id, code=asset_class.code, name=asset_class.name)


def _parse_percent_bps(value: str) -> int:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(
            f"{value!r} is not a valid percent.", code="VALIDATION_ERROR"
        ) from exc
    if parsed != parsed.quantize(PERCENT_SCALE):
        raise ValidationError(
            f"{value!r} must have exactly 2 decimal places.", code="VALIDATION_ERROR"
        )
    return string_to_basis_points(str(parsed))


def _bps_to_percent_string(total_bps: int) -> str:
    return percent_to_string(total_bps)


def _template_to_list_response(
    template: AllocationTemplateEntity,
) -> AllocationTemplateListEntryResponse:
    total_bps = sum(entry.percent_bps for entry in template.allocations_json.allocations)
    return AllocationTemplateListEntryResponse(
        id=template.id,
        version=template.version,
        risk_band=template.risk_band,
        allocations=[
            AllocationEntryRequest(
                asset_class_id=entry.asset_class_id, percent=percent_to_string(entry.percent_bps)
            )
            for entry in template.allocations_json.allocations
        ],
        total_percent=percent_to_string(total_bps),
        published_at=template.published_at,
        is_active=template.is_active,
    )
