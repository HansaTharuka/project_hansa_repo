"""Closed sets backing every CHECK-constrained column (data-models.md §4).

Each enum is the single source of the literal values; a column annotated with
one of these rejects an out-of-set value at the Pydantic boundary rather than
relying on the database CHECK alone.
"""

from enum import StrEnum


class Role(StrEnum):
    """User.role and AuditLogEntry.actor_role (data-models.md §4.1, §4.14)."""

    CUSTOMER = "customer"
    ADVISOR = "advisor"
    ADMIN = "admin"
    COMPLIANCE = "compliance"


class RiskBand(StrEnum):
    """Risk bands, uppercase as stored (data-models.md §4.4, §4.6, §4.13)."""

    CONSERVATIVE = "CONSERVATIVE"
    MODERATE = "MODERATE"
    AGGRESSIVE = "AGGRESSIVE"


class RecommendationStatus(StrEnum):
    """RebalancingRecommendation.status — one-shot transition out of pending."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class TradeAction(StrEnum):
    """The action inside proposed_actions_json (data-models.md §4.12)."""

    BUY = "BUY"
    SELL = "SELL"


class AuditEntityType(StrEnum):
    """AuditLogEntry.entity_type — the nine auditable entities (data-models.md §4.14)."""

    RISK_BAND_ASSIGNMENT = "RiskBandAssignment"
    ALLOCATION_RECOMMENDATION = "AllocationRecommendation"
    REBALANCING_RECOMMENDATION = "RebalancingRecommendation"
    ADVISOR_OVERRIDE = "AdvisorOverride"
    MANUAL_RECOMMENDATION = "ManualRecommendation"
    RISK_BAND_RULE = "RiskBandRule"
    ALLOCATION_TEMPLATE = "AllocationTemplate"
    ASSET_CLASS = "AssetClass"
    REBALANCING_THRESHOLD = "RebalancingThreshold"


class AuditAction(StrEnum):
    """AuditLogEntry.action — the twelve audited verbs (data-models.md §4.14)."""

    ASSIGN_RISK_BAND = "ASSIGN_RISK_BAND"
    GENERATE_ALLOCATION_RECOMMENDATION = "GENERATE_ALLOCATION_RECOMMENDATION"
    GENERATE_REBALANCING_RECOMMENDATION = "GENERATE_REBALANCING_RECOMMENDATION"
    ACCEPT_REBALANCING_RECOMMENDATION = "ACCEPT_REBALANCING_RECOMMENDATION"
    DISMISS_REBALANCING_RECOMMENDATION = "DISMISS_REBALANCING_RECOMMENDATION"
    OVERRIDE_RISK_BAND = "OVERRIDE_RISK_BAND"
    LOG_MANUAL_RECOMMENDATION = "LOG_MANUAL_RECOMMENDATION"
    PUBLISH_RISK_BAND_RULE = "PUBLISH_RISK_BAND_RULE"
    PUBLISH_ALLOCATION_TEMPLATE = "PUBLISH_ALLOCATION_TEMPLATE"
    PUBLISH_REBALANCING_THRESHOLD = "PUBLISH_REBALANCING_THRESHOLD"
    CREATE_ASSET_CLASS = "CREATE_ASSET_CLASS"
    UPDATE_ASSET_CLASS = "UPDATE_ASSET_CLASS"
