"""Admin publish service (E10-S2) — the server-side validation gates in front
of E10-S1's versioned-publish repositories.

`publish_allocation_template`/`publish_risk_band_rule` re-assert the
sum-to-10000-bps and >=6-question rules here, before any repository call
(AC1, AC2) — `recommendation.repository.publish_template` already rejects an
invalid sum too, but this is the layer a router talks to, so no invalid
request ever reaches a repository at all. A genuine concurrent-publish race
for the identical next version surfaces as the repository's `IntegrityError`
(E10-S1's `UNIQUE(version)`/`UNIQUE(risk_band, version)` index); it is caught
here and re-raised as `ConflictError` so exactly one of two racing publishes
succeeds (AC3). Every successful publish or asset-class write calls the
audit-writer exactly once (AC4). Asset-class `code` uniqueness is checked
before either insert or update ever reaches the repository (AC5).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.admin.repository import update_asset_class as _update_asset_class_row
from src.domain.audit.service import write_audit_entry
from src.domain.holdings.repository import (
    get_asset_class_by_code,
    insert_asset_class,
    list_asset_classes,
)
from src.domain.rebalancing.threshold_repository import publish_threshold
from src.domain.recommendation.repository import list_templates, publish_template
from src.domain.risk_profile.repository import list_rule_versions, publish_rule
from src.types.entities import (
    AllocationSet,
    AllocationTemplate,
    AssetClass,
    Questionnaire,
    RebalancingThreshold,
    RiskBandRule,
    ScoringRules,
)
from src.types.errors import ConflictError, ValidationError

MIN_QUESTIONNAIRE_QUESTIONS = 6
ALLOCATION_TOTAL_BPS = 10000


def publish_risk_band_rule(
    session: Session,
    *,
    questionnaire: Questionnaire,
    scoring_rules: ScoringRules,
    actor_id: int,
    actor_role: str,
) -> RiskBandRule:
    """Publish the next `RiskBandRule` version (AC2, AC3, AC4)."""
    if len(questionnaire.questions) < MIN_QUESTIONNAIRE_QUESTIONS:
        raise ValidationError(
            f"questionnaire_json must contain at least {MIN_QUESTIONNAIRE_QUESTIONS} "
            f"questions, got {len(questionnaire.questions)}.",
            code="QUESTIONNAIRE_TOO_SHORT",
            details={"question_count": len(questionnaire.questions)},
        )
    rule = _publish_with_conflict_translation(
        lambda: publish_rule(
            session,
            questionnaire=questionnaire,
            scoring_rules=scoring_rules,
            published_at=_now_iso(),
        ),
        session=session,
    )
    write_audit_entry(
        session,
        entity_type="RiskBandRule",
        entity_id=str(rule.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="PUBLISH_RISK_BAND_RULE",
        details={"version": rule.version},
    )
    return rule


def publish_allocation_template(
    session: Session,
    *,
    risk_band: str,
    allocations: AllocationSet,
    actor_id: int,
    actor_role: str,
) -> AllocationTemplate:
    """Publish the next `AllocationTemplate` version for `risk_band` (AC1, AC3, AC4)."""
    total_bps = sum(entry.percent_bps for entry in allocations.allocations)
    if total_bps != ALLOCATION_TOTAL_BPS:
        raise ValidationError(
            f"Allocation percentages must sum to exactly {ALLOCATION_TOTAL_BPS} bps, "
            f"got {total_bps}.",
            code="TEMPLATE_SUM_INVALID",
            details={"sum_bps": total_bps},
        )
    template = _publish_with_conflict_translation(
        lambda: publish_template(
            session, risk_band=risk_band, allocations=allocations, published_at=_now_iso()
        ),
        session=session,
    )
    write_audit_entry(
        session,
        entity_type="AllocationTemplate",
        entity_id=str(template.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="PUBLISH_ALLOCATION_TEMPLATE",
        details={"risk_band": risk_band, "version": template.version},
    )
    return template


def publish_rebalancing_threshold(
    session: Session, *, threshold_bps: int, actor_id: int, actor_role: str
) -> RebalancingThreshold:
    """Publish the next `RebalancingThreshold` version (AC3, AC4)."""
    threshold = _publish_with_conflict_translation(
        lambda: publish_threshold(session, threshold_bps=threshold_bps, published_at=_now_iso()),
        session=session,
    )
    write_audit_entry(
        session,
        entity_type="RebalancingThreshold",
        entity_id=str(threshold.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="PUBLISH_REBALANCING_THRESHOLD",
        details={"version": threshold.version},
    )
    return threshold


def list_allocation_templates_for_admin(
    session: Session, *, risk_band: str | None = None
) -> list[AllocationTemplate]:
    """Every `AllocationTemplate` version, active and superseded, optionally
    scoped to one `risk_band` (E10-S3 AC5). A read, so no audit entry."""
    return list_templates(session, risk_band=risk_band)


def create_asset_class_with_audit(
    session: Session, *, code: str, name: str, actor_id: int, actor_role: str
) -> AssetClass:
    """Create one `AssetClass`, rejecting a duplicate `code` first (AC5)."""
    if get_asset_class_by_code(session, code) is not None:
        raise ConflictError(
            f"AssetClass code {code!r} is already in use.",
            code="DUPLICATE_ASSET_CLASS_CODE",
            details={"code": code},
        )
    asset_class = insert_asset_class(session, code=code, name=name)
    write_audit_entry(
        session,
        entity_type="AssetClass",
        entity_id=str(asset_class.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="CREATE_ASSET_CLASS",
        details={"code": code},
    )
    return asset_class


def update_asset_class_with_audit(
    session: Session,
    *,
    asset_class_id: int,
    code: str | None,
    name: str | None,
    actor_id: int,
    actor_role: str,
) -> AssetClass:
    """Edit `code`/`name` in place, rejecting a duplicate `code` first (AC5)."""
    if code is not None:
        existing = get_asset_class_by_code(session, code)
        if existing is not None and existing.id != asset_class_id:
            raise ConflictError(
                f"AssetClass code {code!r} is already in use.",
                code="DUPLICATE_ASSET_CLASS_CODE",
                details={"code": code},
            )
    asset_class = _update_asset_class_row(
        session, asset_class_id=asset_class_id, code=code, name=name
    )
    write_audit_entry(
        session,
        entity_type="AssetClass",
        entity_id=str(asset_class.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="UPDATE_ASSET_CLASS",
        details={"asset_class_id": asset_class_id},
    )
    return asset_class


def list_asset_classes_for_admin(session: Session) -> list[AssetClass]:
    """Every `AssetClass`, ordered by `code` ascending (api-contracts.md §12.6).
    A read, so no audit entry. `holdings.repository.list_asset_classes` orders
    by insertion id for its other callers, so the code-ordering happens here,
    not by changing that repository function."""
    return sorted(list_asset_classes(session), key=lambda asset_class: asset_class.code)


def list_risk_band_rules_for_admin(session: Session) -> list[RiskBandRule]:
    """Every `RiskBandRule` version, active and superseded, ordered by
    `version` ascending (api-contracts.md §12.2). A read, so no audit entry."""
    return list_rule_versions(session)


def _publish_with_conflict_translation[T](
    publish_call: Callable[[], T], *, session: Session
) -> T:
    try:
        return publish_call()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "Another publish already claimed the next version.", code="VERSION_CONFLICT"
        ) from exc


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
