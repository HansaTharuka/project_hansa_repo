"""`domain/admin/service.py` — publish_risk_band_rule() / publish_allocation_template()
/ publish_rebalancing_threshold() / create_asset_class_with_audit() /
update_asset_class_with_audit() (E10-S2 AC1-AC5; ut-153..ut-157)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import AllocationTemplate as AllocationTemplateRow
from src.domain.admin.service import (
    create_asset_class_with_audit,
    publish_allocation_template,
    publish_rebalancing_threshold,
    publish_risk_band_rule,
    update_asset_class_with_audit,
)
from src.domain.holdings.repository import insert_asset_class
from src.types.entities import (
    AllocationEntry,
    AllocationSet,
    BandRange,
    Question,
    Questionnaire,
    QuestionOption,
    ScoringRules,
)
from src.types.errors import ConflictError, ValidationError

ACTOR = {"actor_id": 1, "actor_role": "admin"}

SIX_QUESTIONS = Questionnaire(
    questions=[
        Question(
            question_id=f"Q{i}",
            text=f"Question {i}?",
            options=[QuestionOption(value="low", label="Low", points=1)],
        )
        for i in range(1, 7)
    ]
)
FIVE_QUESTIONS = Questionnaire(questions=SIX_QUESTIONS.questions[:5])
SCORING_RULES = ScoringRules(
    bands=[BandRange(risk_band="CONSERVATIVE", min_points=0, max_points=100)]
)


def _asset_class_id(session: Session, code: str) -> int:
    asset_class = insert_asset_class(session, code=code, name=code)
    session.commit()
    return asset_class.id


def test_publishing_a_template_whose_bps_sum_to_9900_is_rejected_with_no_row_written(
    db_session: Session,
) -> None:
    asset_class_id = _asset_class_id(db_session, "AC_9900")

    with pytest.raises(ValidationError) as excinfo:
        publish_allocation_template(
            db_session,
            risk_band="MODERATE",
            allocations=AllocationSet(
                allocations=[AllocationEntry(asset_class_id=asset_class_id, percent_bps=9900)]
            ),
            **ACTOR,
        )

    assert excinfo.value.code == "TEMPLATE_SUM_INVALID"
    assert db_session.query(AllocationTemplateRow).count() == 0


def test_publishing_a_template_whose_bps_sum_to_10100_is_rejected_with_no_row_written(
    db_session: Session,
) -> None:
    asset_class_id = _asset_class_id(db_session, "AC_10100")

    with pytest.raises(ValidationError) as excinfo:
        publish_allocation_template(
            db_session,
            risk_band="MODERATE",
            allocations=AllocationSet(
                allocations=[AllocationEntry(asset_class_id=asset_class_id, percent_bps=10100)]
            ),
            **ACTOR,
        )

    assert excinfo.value.code == "TEMPLATE_SUM_INVALID"
    assert db_session.query(AllocationTemplateRow).count() == 0


def test_publishing_a_rule_with_fewer_than_six_questions_is_rejected_with_no_row_written(
    db_session: Session,
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        publish_risk_band_rule(
            db_session, questionnaire=FIVE_QUESTIONS, scoring_rules=SCORING_RULES, **ACTOR
        )

    assert excinfo.value.code == "QUESTIONNAIRE_TOO_SHORT"
    from src.db.models import RiskBandRule as RiskBandRuleRow

    assert db_session.query(RiskBandRuleRow).count() == 0


def test_a_valid_rule_publish_succeeds_and_audits_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.admin.service.write_audit_entry", spy)

    rule = publish_risk_band_rule(
        db_session, questionnaire=SIX_QUESTIONS, scoring_rules=SCORING_RULES, **ACTOR
    )

    assert rule.version == 1
    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "RiskBandRule"


def test_a_valid_template_publish_succeeds_and_audits_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset_class_id = _asset_class_id(db_session, "AC_VALID")
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.admin.service.write_audit_entry", spy)

    template = publish_allocation_template(
        db_session,
        risk_band="CONSERVATIVE",
        allocations=AllocationSet(
            allocations=[AllocationEntry(asset_class_id=asset_class_id, percent_bps=10000)]
        ),
        **ACTOR,
    )

    assert template.version == 1
    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "AllocationTemplate"


def test_a_valid_threshold_publish_succeeds_and_audits_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.admin.service.write_audit_entry", spy)

    threshold = publish_rebalancing_threshold(db_session, threshold_bps=500, **ACTOR)

    assert threshold.version == 1
    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "RebalancingThreshold"


def test_two_concurrent_rule_publishes_for_the_same_version_conflict_exactly_one_loses(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_integrity_error(*args: object, **kwargs: object) -> None:
        raise IntegrityError(
            "INSERT INTO risk_band_rule ...", {}, Exception("UNIQUE constraint failed")
        )

    monkeypatch.setattr("src.domain.admin.service.publish_rule", _raise_integrity_error)

    with pytest.raises(ConflictError) as excinfo:
        publish_risk_band_rule(
            db_session, questionnaire=SIX_QUESTIONS, scoring_rules=SCORING_RULES, **ACTOR
        )

    assert excinfo.value.code == "VERSION_CONFLICT"


def test_creating_an_asset_class_with_a_code_already_in_use_is_rejected(
    db_session: Session,
) -> None:
    _asset_class_id(db_session, "DUP_CODE")

    with pytest.raises(ConflictError) as excinfo:
        create_asset_class_with_audit(db_session, code="DUP_CODE", name="Second", **ACTOR)

    assert excinfo.value.code == "DUPLICATE_ASSET_CLASS_CODE"


def test_creating_a_new_asset_class_succeeds_and_audits_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.admin.service.write_audit_entry", spy)

    asset_class = create_asset_class_with_audit(
        db_session, code="NEW_CODE", name="New Asset Class", **ACTOR
    )

    assert asset_class.code == "NEW_CODE"
    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "AssetClass"


def test_updating_an_asset_class_to_a_code_used_by_another_is_rejected(
    db_session: Session,
) -> None:
    _asset_class_id(db_session, "TAKEN")
    other_id = _asset_class_id(db_session, "OTHER")

    with pytest.raises(ConflictError) as excinfo:
        update_asset_class_with_audit(
            db_session, asset_class_id=other_id, code="TAKEN", name=None, **ACTOR
        )

    assert excinfo.value.code == "DUPLICATE_ASSET_CLASS_CODE"


def test_updating_an_asset_class_to_its_own_current_code_is_allowed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset_class_id = _asset_class_id(db_session, "SELF_CODE")
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.admin.service.write_audit_entry", spy)

    updated = update_asset_class_with_audit(
        db_session, asset_class_id=asset_class_id, code="SELF_CODE", name="Renamed", **ACTOR
    )

    assert updated.name == "Renamed"
    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "AssetClass"
