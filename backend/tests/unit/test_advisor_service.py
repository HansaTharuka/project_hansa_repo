"""`domain/advisor/service.py` — override_risk_band(), log_manual_recommendation()
(E9-S2 AC1-AC5; ut-188..ut-192)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.advisor.service import log_manual_recommendation, override_risk_band
from src.domain.auth.repository import create_user
from src.domain.risk_profile.repository import (
    get_latest_assignment,
    insert_assignment,
    publish_rule,
)
from src.types.entities import BandRange, Question, Questionnaire, QuestionOption, ScoringRules
from src.types.errors import ConflictError, NotFoundError, ValidationError

QUESTIONNAIRE = Questionnaire(
    questions=[
        Question(
            question_id=f"Q{i}", text=f"Question {i}?",
            options=[QuestionOption(value="low", label="Low", points=1)],
        )
        for i in range(1, 7)
    ]
)
SCORING_RULES = ScoringRules(bands=[BandRange(risk_band="MODERATE", min_points=0, max_points=100)])


def _seed_customer(session: Session, email: str) -> int:
    user_seed = build_user(email=email)
    user = create_user(
        session, email=user_seed.email, password_hash=user_seed.password_hash,
        role=user_seed.role, created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id)
    customer = Customer(
        user_id=customer_seed.user_id, kyc_verified=customer_seed.kyc_verified,
        created_at=customer_seed.created_at,
    )
    session.add(customer)
    session.commit()
    return customer.id


def _seed_advisor(session: Session, email: str) -> int:
    user_seed = build_user(email=email, role="advisor")
    user = create_user(
        session, email=user_seed.email, password_hash=user_seed.password_hash,
        role="advisor", created_at=user_seed.created_at,
    )
    session.commit()
    return user.id


def _publish_rule(session: Session) -> None:
    publish_rule(
        session, questionnaire=QUESTIONNAIRE, scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    session.commit()


def _assign_band(session: Session, *, customer_id: int, risk_band: str) -> None:
    insert_assignment(
        session, customer_id=customer_id, risk_band=risk_band, rule_version=1,
        assigned_at="2026-09-01T09:00:00Z",
    )
    session.commit()


def test_a_valid_override_creates_an_override_row_and_a_new_assignment_reflecting_new_band(
    db_session: Session,
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "advisorsvc.customer1@wealthwise.test")
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor1@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")

    result = override_risk_band(
        db_session, customer_id=customer_id, advisor_id=advisor_id, new_band="CONSERVATIVE",
        reason="Client reported imminent liquidity need.", note=None,
        actor_id=advisor_id, actor_role="advisor",
    )

    assert result.new_band == "CONSERVATIVE"
    latest = get_latest_assignment(db_session, customer_id)
    assert latest is not None
    assert latest.risk_band == "CONSERVATIVE"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_an_override_with_a_blank_reason_is_rejected_and_writes_no_rows(
    db_session: Session, reason: str | None
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "advisorsvc.customer2@wealthwise.test")
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor2@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")

    with pytest.raises(ValidationError) as excinfo:
        override_risk_band(
            db_session, customer_id=customer_id, advisor_id=advisor_id, new_band="CONSERVATIVE",
            reason=reason, note=None, actor_id=advisor_id, actor_role="advisor",
        )

    assert excinfo.value.code == "REASON_REQUIRED"
    from sqlalchemy import text

    override_count = db_session.execute(
        text("SELECT COUNT(*) FROM advisor_override WHERE customer_id = :id"), {"id": customer_id}
    ).scalar_one()
    assignment_count = db_session.execute(
        text(
            "SELECT COUNT(*) FROM risk_band_assignment "
            "WHERE customer_id = :id AND risk_band = 'CONSERVATIVE'"
        ),
        {"id": customer_id},
    ).scalar_one()
    assert override_count == 0
    assert assignment_count == 0


def test_a_successful_override_invokes_the_audit_writer_exactly_once_with_advisor_override(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "advisorsvc.customer3@wealthwise.test")
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor3@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.advisor.service.write_audit_entry", spy)

    override_risk_band(
        db_session, customer_id=customer_id, advisor_id=advisor_id, new_band="AGGRESSIVE",
        reason="Client increased their risk appetite.", note="Reviewed Q3 statement.",
        actor_id=advisor_id, actor_role="advisor",
    )

    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "AdvisorOverride"


def test_logging_a_manual_recommendation_records_the_note_and_audits_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    customer_id = _seed_customer(db_session, "advisorsvc.customer4@wealthwise.test")
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor4@wealthwise.test")

    def _fake_write_audit_entry(*args: object, **kwargs: object) -> object:
        del args
        from src.types.entities import AuditLogEntry

        return AuditLogEntry(
            id=512,
            entity_type=kwargs["entity_type"],  # type: ignore[arg-type]
            entity_id=kwargs["entity_id"],  # type: ignore[arg-type]
            actor_id=kwargs["actor_id"],  # type: ignore[arg-type]
            actor_role=kwargs["actor_role"],  # type: ignore[arg-type]
            action=kwargs["action"],  # type: ignore[arg-type]
            timestamp="2026-09-03T14:10:00Z",
            details_json=kwargs["details"],  # type: ignore[arg-type]
        )

    spy = MagicMock(wraps=_fake_write_audit_entry)
    monkeypatch.setattr("src.domain.advisor.service.write_audit_entry", spy)

    log_manual_recommendation(
        db_session, customer_id=customer_id, advisor_id=advisor_id,
        note="Recommended increasing cash weighting ahead of Q4.",
        actor_id=advisor_id, actor_role="advisor",
    )

    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "ManualRecommendation"
    expected_note = "Recommended increasing cash weighting ahead of Q4."
    assert spy.call_args.kwargs["details"]["note"] == expected_note
    assert spy.call_args.kwargs["entity_id"] == str(customer_id)


def test_overriding_a_nonexistent_customer_raises_not_found(db_session: Session) -> None:
    _publish_rule(db_session)
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor5@wealthwise.test")

    with pytest.raises(NotFoundError) as excinfo:
        override_risk_band(
            db_session, customer_id=999999, advisor_id=advisor_id, new_band="MODERATE",
            reason="Some reason.", note=None, actor_id=advisor_id, actor_role="advisor",
        )

    assert excinfo.value.code == "CUSTOMER_NOT_FOUND"


def test_overriding_a_customer_with_no_prior_assignment_raises_conflict(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "advisorsvc.customer6@wealthwise.test")
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor6@wealthwise.test")

    with pytest.raises(ConflictError) as excinfo:
        override_risk_band(
            db_session, customer_id=customer_id, advisor_id=advisor_id, new_band="MODERATE",
            reason="Some reason.", note=None, actor_id=advisor_id, actor_role="advisor",
        )

    assert excinfo.value.code == "NO_PRIOR_ASSIGNMENT"


@pytest.mark.parametrize("note", [None, "", "   ", "x" * 2001])
def test_logging_a_manual_recommendation_with_an_invalid_note_is_rejected(
    db_session: Session, note: str | None
) -> None:
    customer_id = _seed_customer(db_session, "advisorsvc.customer7@wealthwise.test")
    advisor_id = _seed_advisor(db_session, "advisorsvc.advisor7@wealthwise.test")

    with pytest.raises(ValidationError) as excinfo:
        log_manual_recommendation(
            db_session, customer_id=customer_id, advisor_id=advisor_id, note=note,
            actor_id=advisor_id, actor_role="advisor",
        )

    assert excinfo.value.code == "NOTE_REQUIRED"
