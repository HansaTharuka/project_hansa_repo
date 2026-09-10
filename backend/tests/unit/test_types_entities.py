"""E1-S1 AC1–AC3 — entity shape, fixed-point typing, closed enums, error hierarchy.

Covers ut-001, ut-002, ut-003, ut-026 (shape and scalar types), ut-004, ut-005
(money and percent typing), ut-007 – ut-010, ut-027 (closed enums) and ut-028
(errors.py is not a stub).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from src.types import entities, errors
from src.types.enums import (
    AuditAction,
    AuditEntityType,
    RecommendationStatus,
    RiskBand,
    Role,
    TradeAction,
)

# data-models.md §4 column lists, plus the four additive columns documented in §1.1.
EXPECTED_FIELDS: dict[str, set[str]] = {
    "User": {"id", "email", "password_hash", "role", "created_at"},
    "Customer": {"id", "user_id", "kyc_verified", "created_at"},
    "RiskProfileAnswer": {"id", "customer_id", "question_id", "answer_value", "submitted_at"},
    "RiskBandAssignment": {"id", "customer_id", "risk_band", "rule_version", "assigned_at"},
    "RiskBandRule": {
        "id", "version", "questionnaire_json", "scoring_rules_json", "published_at", "is_active",
    },
    "AllocationTemplate": {
        "id", "version", "risk_band", "allocations_json", "published_at", "is_active",
    },
    "Goal": {
        "id", "customer_id", "target_amount", "target_date", "priority", "created_at", "updated_at",
    },
    "GoalProgressSnapshot": {
        "id", "goal_id", "current_value", "percent_complete", "snapshot_at", "price_date",
    },
    "AssetClass": {"id", "code", "name"},
    "NavSnapshot": {"id", "asset_class_id", "price_date", "nav_value"},
    "Holding": {"id", "customer_id", "asset_class_id", "current_value", "as_of_date"},
    "RebalancingRecommendation": {
        "id", "customer_id", "recommendation_id", "proposed_actions_json", "status",
        "generated_at", "resolved_at",
    },
    "AdvisorOverride": {
        "id", "customer_id", "advisor_id", "previous_band", "new_band", "reason", "note",
        "created_at",
    },
    "AuditLogEntry": {
        "id", "entity_type", "entity_id", "actor_id", "actor_role", "action", "timestamp",
        "details_json",
    },
    "RebalancingThreshold": {"id", "version", "threshold_bps", "published_at", "is_active"},
}

BRD_ENTITY_NAMES = [name for name in EXPECTED_FIELDS if name != "RebalancingThreshold"]

# Only these two columns are nullable (data-models.md §4.12, §4.13).
OPTIONAL_FIELDS = {("RebalancingRecommendation", "resolved_at"), ("AdvisorOverride", "note")}

MONEY_FIELDS = [
    ("Goal", "target_amount"),
    ("GoalProgressSnapshot", "current_value"),
    ("NavSnapshot", "nav_value"),
    ("Holding", "current_value"),
    ("ProposedAction", "amount"),
]

TIMESTAMP_AND_DATE_FIELDS = {
    "created_at", "updated_at", "submitted_at", "assigned_at", "published_at", "generated_at",
    "resolved_at", "snapshot_at", "timestamp", "target_date", "price_date", "as_of_date",
}
INT_SCALAR_FIELDS = {"priority", "version", "rule_version"}
BOOL_FIELDS = {"kyc_verified", "is_active"}
# TEXT identifiers that are deliberately not integer foreign keys (data-models.md §4.3/§4.12/§4.14).
STRING_ID_FIELDS = {"question_id", "recommendation_id", "entity_id"}
JSON_FIELDS = [
    ("RiskBandRule", "questionnaire_json"),
    ("RiskBandRule", "scoring_rules_json"),
    ("AllocationTemplate", "allocations_json"),
    ("RebalancingRecommendation", "proposed_actions_json"),
    ("AuditLogEntry", "details_json"),
]

VALID_USER: dict[str, object] = {
    "id": 3,
    "email": "customer03@wealthwise.test",
    "password_hash": "$2b$12$K1x0Qe3xk8Yd2m1u0V4hQeU2rTn6bY7wCq0aZs9dLf3pR1oJ5mN8i",
    "role": Role.CUSTOMER,
    "created_at": "2026-09-01T09:00:00Z",
}
VALID_ASSIGNMENT: dict[str, object] = {
    "id": 12,
    "customer_id": 3,
    "risk_band": RiskBand.MODERATE,
    "rule_version": 1,
    "assigned_at": "2026-09-03T10:15:00Z",
}
VALID_ACTIONS: dict[str, object] = {
    "actions": [
        {
            "asset_class_id": 1,
            "asset_class_code": "EQ_DM",
            "action": "SELL",
            "amount": Decimal("3200.00"),
            "units": Decimal("24.1600"),
            "drift_percent": Decimal("6.40"),
        }
    ],
    "threshold_bps": 500,
    "threshold_version": 1,
}
VALID_RECOMMENDATION: dict[str, object] = {
    "id": 9,
    "customer_id": 3,
    "recommendation_id": "b6f0c2a4-1d3e-4f58-9a71-0c2e5d8b7a10",
    "proposed_actions_json": VALID_ACTIONS,
    "status": RecommendationStatus.PENDING,
    "generated_at": "2026-09-04T08:00:00Z",
    "resolved_at": None,
}
VALID_AUDIT_ENTRY: dict[str, object] = {
    "id": 501,
    "entity_type": AuditEntityType.RISK_BAND_ASSIGNMENT,
    "entity_id": "12",
    "actor_id": 3,
    "actor_role": Role.CUSTOMER,
    "action": AuditAction.ASSIGN_RISK_BAND,
    "timestamp": "2026-09-03T10:15:00Z",
    "details_json": {"customer_id": 3, "risk_band": "MODERATE", "rule_version": 1},
}


def model_for(name: str) -> type[BaseModel]:
    model = getattr(entities, name)
    assert isinstance(model, type) and issubclass(model, BaseModel), f"{name} is not a model"
    return model


def annotation_of(model_name: str, field: str) -> object:
    return model_for(model_name).model_fields[field].annotation


class TestEntityInventory:
    """ut-001, ut-003 — every BRD §9 entity plus RebalancingThreshold is modelled."""

    @pytest.mark.parametrize("entity_name", BRD_ENTITY_NAMES)
    def test_brd_entity_is_defined_as_a_pydantic_model(self, entity_name: str) -> None:
        assert issubclass(model_for(entity_name), BaseModel)

    def test_all_fourteen_brd_entities_are_present(self) -> None:
        assert len(BRD_ENTITY_NAMES) == 14

    def test_rebalancing_threshold_is_defined(self) -> None:
        assert set(model_for("RebalancingThreshold").model_fields) == {
            "id", "version", "threshold_bps", "published_at", "is_active"
        }

    def test_threshold_bps_is_the_one_integer_percent_quantity(self) -> None:
        assert annotation_of("RebalancingThreshold", "threshold_bps") is int


class TestFieldNames:
    """ut-002 — field names equal the data-models.md §4 column lists exactly."""

    @pytest.mark.parametrize(("entity_name", "expected"), sorted(EXPECTED_FIELDS.items()))
    def test_field_names_match_the_column_list(
        self, entity_name: str, expected: set[str]
    ) -> None:
        assert set(model_for(entity_name).model_fields) == expected

    def test_password_hash_is_present_on_the_persistence_mirror(self) -> None:
        # entities.py mirrors the table; never-serialise is types/responses.py's job (E2-S2 AC4).
        assert "password_hash" in model_for("User").model_fields


class TestScalarTypesAndNullability:
    """ut-026 — scalar annotations and exact nullability."""

    @pytest.mark.parametrize("entity_name", sorted(EXPECTED_FIELDS))
    def test_identifier_fields_are_int(self, entity_name: str) -> None:
        for field in EXPECTED_FIELDS[entity_name]:
            if (field == "id" or field.endswith("_id")) and field not in STRING_ID_FIELDS:
                assert annotation_of(entity_name, field) is int, f"{entity_name}.{field}"

    @pytest.mark.parametrize("entity_name", sorted(EXPECTED_FIELDS))
    def test_scalar_field_annotations_match_the_conventions(self, entity_name: str) -> None:
        for field in EXPECTED_FIELDS[entity_name]:
            annotation = annotation_of(entity_name, field)
            if field in INT_SCALAR_FIELDS:
                assert annotation is int, f"{entity_name}.{field}"
            elif field in BOOL_FIELDS:
                assert annotation is bool, f"{entity_name}.{field}"
            elif field in STRING_ID_FIELDS:
                assert annotation is str, f"{entity_name}.{field}"
            elif field in TIMESTAMP_AND_DATE_FIELDS:
                assert str in (annotation, *get_args(annotation)), f"{entity_name}.{field}"

    @pytest.mark.parametrize(("entity_name", "field"), JSON_FIELDS)
    def test_json_columns_are_typed_containers_not_raw_strings(
        self, entity_name: str, field: str
    ) -> None:
        annotation = annotation_of(entity_name, field)
        assert annotation is not str and annotation is not Any
        is_model = isinstance(annotation, type) and issubclass(annotation, BaseModel)
        assert is_model or get_origin(annotation) is dict, f"{entity_name}.{field}"

    @pytest.mark.parametrize("entity_name", sorted(EXPECTED_FIELDS))
    def test_only_the_two_documented_columns_are_nullable(self, entity_name: str) -> None:
        for field, info in model_for(entity_name).model_fields.items():
            if (entity_name, field) in OPTIONAL_FIELDS:
                assert type(None) in get_args(info.annotation), f"{entity_name}.{field}"
            else:
                assert info.is_required(), f"{entity_name}.{field} must be required"


class TestFixedPointTyping:
    """ut-004, ut-005 — NFR-01 money and percentage typing."""

    @pytest.mark.parametrize(("entity_name", "field"), MONEY_FIELDS)
    def test_money_fields_are_decimal(self, entity_name: str, field: str) -> None:
        assert annotation_of(entity_name, field) is Decimal

    def test_proposed_action_units_are_decimal(self) -> None:
        assert annotation_of("ProposedAction", "units") is Decimal

    def test_percent_complete_is_decimal(self) -> None:
        assert annotation_of("GoalProgressSnapshot", "percent_complete") is Decimal

    def test_allocation_entries_store_integer_basis_points(self) -> None:
        assert annotation_of("AllocationEntry", "percent_bps") is int

    def test_drift_percent_is_a_signed_decimal(self) -> None:
        assert annotation_of("ProposedAction", "drift_percent") is Decimal
        action = entities.ProposedAction.model_validate(VALID_ACTIONS["actions"][0])  # type: ignore[index]
        assert action.drift_percent == Decimal("6.40")

    def test_negative_drift_percent_is_accepted(self) -> None:
        payload = dict(VALID_ACTIONS["actions"][0])  # type: ignore[index,arg-type]
        payload["drift_percent"] = Decimal("-6.40")
        assert entities.ProposedAction.model_validate(payload).drift_percent < 0

    def test_no_percent_field_anywhere_in_types_is_a_float(self) -> None:
        derived = {"current_percent", "target_percent", "drift_percent", "percent_complete"}
        for name in dir(entities):
            candidate = getattr(entities, name)
            if not (isinstance(candidate, type) and issubclass(candidate, BaseModel)):
                continue
            for field in derived & set(candidate.model_fields):
                assert candidate.model_fields[field].annotation is Decimal, f"{name}.{field}"


class TestClosedEnums:
    """ut-007 – ut-010, ut-027 — closed sets with exact literal values."""

    def test_role_has_exactly_the_four_brd_values(self) -> None:
        assert {member.value for member in Role} == {"customer", "advisor", "admin", "compliance"}

    def test_risk_band_has_exactly_the_three_uppercase_values(self) -> None:
        assert {member.value for member in RiskBand} == {
            "CONSERVATIVE", "MODERATE", "AGGRESSIVE"
        }

    def test_recommendation_status_has_exactly_the_three_values(self) -> None:
        assert {member.value for member in RecommendationStatus} == {
            "pending", "accepted", "dismissed"
        }

    def test_trade_action_has_exactly_buy_and_sell(self) -> None:
        assert {member.value for member in TradeAction} == {"BUY", "SELL"}

    def test_audit_entity_type_has_exactly_the_nine_values(self) -> None:
        assert {member.value for member in AuditEntityType} == {
            "RiskBandAssignment", "AllocationRecommendation", "RebalancingRecommendation",
            "AdvisorOverride", "ManualRecommendation", "RiskBandRule", "AllocationTemplate",
            "AssetClass", "RebalancingThreshold",
        }

    def test_audit_action_has_exactly_the_twelve_values(self) -> None:
        assert {member.value for member in AuditAction} == {
            "ASSIGN_RISK_BAND", "GENERATE_ALLOCATION_RECOMMENDATION",
            "GENERATE_REBALANCING_RECOMMENDATION", "ACCEPT_REBALANCING_RECOMMENDATION",
            "DISMISS_REBALANCING_RECOMMENDATION", "OVERRIDE_RISK_BAND",
            "LOG_MANUAL_RECOMMENDATION", "PUBLISH_RISK_BAND_RULE",
            "PUBLISH_ALLOCATION_TEMPLATE", "PUBLISH_REBALANCING_THRESHOLD",
            "CREATE_ASSET_CLASS", "UPDATE_ASSET_CLASS",
        }

    @pytest.mark.parametrize(
        ("entity_name", "field", "enum_type"),
        [
            ("User", "role", Role),
            ("AuditLogEntry", "actor_role", Role),
            ("RiskBandAssignment", "risk_band", RiskBand),
            ("AllocationTemplate", "risk_band", RiskBand),
            ("AdvisorOverride", "previous_band", RiskBand),
            ("AdvisorOverride", "new_band", RiskBand),
            ("RebalancingRecommendation", "status", RecommendationStatus),
            ("ProposedAction", "action", TradeAction),
            ("AuditLogEntry", "entity_type", AuditEntityType),
            ("AuditLogEntry", "action", AuditAction),
            ("BandRange", "risk_band", RiskBand),
        ],
    )
    def test_enum_constrained_field_is_annotated_with_its_enum(
        self, entity_name: str, field: str, enum_type: type
    ) -> None:
        assert annotation_of(entity_name, field) is enum_type

    def test_unknown_role_is_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            entities.User.model_validate({**VALID_USER, "role": "superuser"})

    def test_lowercase_risk_band_is_not_coerced(self) -> None:
        with pytest.raises(PydanticValidationError):
            entities.RiskBandAssignment.model_validate(
                {**VALID_ASSIGNMENT, "risk_band": "conservative"}
            )

    def test_uppercase_status_is_not_coerced(self) -> None:
        with pytest.raises(PydanticValidationError):
            entities.RebalancingRecommendation.model_validate(
                {**VALID_RECOMMENDATION, "status": "PENDING"}
            )

    def test_unknown_audit_action_is_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            entities.AuditLogEntry.model_validate({**VALID_AUDIT_ENTRY, "action": "DROP_TABLE"})

    def test_valid_payloads_construct_cleanly(self) -> None:
        assert entities.User.model_validate(VALID_USER).role is Role.CUSTOMER
        assert entities.AuditLogEntry.model_validate(VALID_AUDIT_ENTRY).actor_id == 3
        assert entities.RebalancingRecommendation.model_validate(
            VALID_RECOMMENDATION
        ).resolved_at is None


class TestDomainErrors:
    """ut-028 — errors.py carries the api-contracts.md §1.4 envelope fields."""

    @pytest.mark.parametrize(
        "error_class", [errors.ValidationError, errors.NotFoundError, errors.ConflictError]
    )
    def test_subclass_derives_from_the_base_domain_error(
        self, error_class: type[errors.DomainError]
    ) -> None:
        assert issubclass(error_class, errors.DomainError)

    @pytest.mark.parametrize(
        "error_class", [errors.ValidationError, errors.NotFoundError, errors.ConflictError]
    )
    def test_subclass_instance_carries_a_non_empty_code(
        self, error_class: type[errors.DomainError]
    ) -> None:
        raised = error_class("Allocation percentages must sum to exactly 100.")
        assert isinstance(raised.code, str) and raised.code

    def test_code_can_be_specialised_per_call_site(self) -> None:
        raised = errors.NotFoundError("Goal 7 does not exist", code="GOAL_NOT_FOUND")
        assert raised.code == "GOAL_NOT_FOUND"

    def test_details_are_an_optional_mapping(self) -> None:
        raised = errors.ValidationError("Sum invalid", details={"sum_bps": 9900})
        assert raised.details == {"sum_bps": 9900}
        assert errors.ValidationError("Sum invalid").details is None

    def test_domain_errors_are_exceptions_and_keep_their_message(self) -> None:
        raised = errors.ConflictError("Recommendation already resolved")
        assert isinstance(raised, Exception)
        assert str(raised) == "Recommendation already resolved"
