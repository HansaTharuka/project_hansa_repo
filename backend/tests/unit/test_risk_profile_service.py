"""`domain/risk_profile/service.py` — submit_risk_profile() (E4-S2 AC2-AC4,
AC6; ut-132, ut-133, ut-134, ut-136)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.risk_profile.repository import publish_rule
from src.domain.risk_profile.service import get_active_questionnaire, submit_risk_profile
from src.types.entities import (
    BandRange,
    Question,
    Questionnaire,
    QuestionOption,
    ScoringRules,
)
from src.types.errors import NotFoundError, ValidationError

QUESTIONNAIRE = Questionnaire(
    questions=[
        Question(
            question_id=f"Q{i}",
            text=f"Question {i}?",
            options=[
                QuestionOption(value="low", label="Low", points=1),
                QuestionOption(value="high", label="High", points=5),
            ],
        )
        for i in range(1, 7)
    ]
)
SCORING_RULES = ScoringRules(
    bands=[
        BandRange(risk_band="CONSERVATIVE", min_points=6, max_points=13),
        BandRange(risk_band="MODERATE", min_points=14, max_points=22),
        BandRange(risk_band="AGGRESSIVE", min_points=23, max_points=30),
    ]
)
ALL_LOW_ANSWERS = {f"Q{i}": "low" for i in range(1, 7)}


def _seed_customer(session: Session, email: str) -> int:
    user_seed = build_user(email=email)
    user = create_user(
        session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id)
    customer = Customer(
        user_id=customer_seed.user_id,
        kyc_verified=customer_seed.kyc_verified,
        created_at=customer_seed.created_at,
    )
    session.add(customer)
    session.commit()
    return customer.id


def _publish_rule(session: Session) -> None:
    publish_rule(
        session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    session.commit()


def test_a_successful_submission_inserts_one_assignment_with_all_fields_populated(
    db_session: Session,
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "risk.customer1@wealthwise.test")

    assignment = submit_risk_profile(
        db_session,
        customer_id=customer_id,
        answers=ALL_LOW_ANSWERS,
        actor_id=customer_id,
        actor_role="customer",
    )
    db_session.commit()

    assert assignment.customer_id == customer_id
    assert assignment.risk_band == "CONSERVATIVE"
    assert assignment.rule_version == 1
    assert assignment.assigned_at


def test_a_successful_submission_invokes_the_audit_writer_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "risk.customer2@wealthwise.test")
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.risk_profile.service.write_audit_entry", spy)

    submit_risk_profile(
        db_session,
        customer_id=customer_id,
        answers=ALL_LOW_ANSWERS,
        actor_id=customer_id,
        actor_role="customer",
    )

    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "RiskBandAssignment"


def test_an_incomplete_answer_set_raises_and_persists_no_answer_or_assignment_rows(
    db_session: Session,
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "risk.customer3@wealthwise.test")
    incomplete = {f"Q{i}": "low" for i in range(1, 6)}

    with pytest.raises(ValidationError) as excinfo:
        submit_risk_profile(
            db_session,
            customer_id=customer_id,
            answers=incomplete,
            actor_id=customer_id,
            actor_role="customer",
        )

    assert excinfo.value.code == "INCOMPLETE_QUESTIONNAIRE"
    from sqlalchemy import text

    answer_count = db_session.execute(
        text("SELECT COUNT(*) FROM risk_profile_answer WHERE customer_id = :id"),
        {"id": customer_id},
    ).scalar_one()
    assignment_count = db_session.execute(
        text("SELECT COUNT(*) FROM risk_band_assignment WHERE customer_id = :id"),
        {"id": customer_id},
    ).scalar_one()
    assert answer_count == 0
    assert assignment_count == 0


def test_submitting_with_no_active_rule_published_raises_not_found(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "risk.customer4@wealthwise.test")

    with pytest.raises(NotFoundError) as excinfo:
        submit_risk_profile(
            db_session,
            customer_id=customer_id,
            answers=ALL_LOW_ANSWERS,
            actor_id=customer_id,
            actor_role="customer",
        )

    assert excinfo.value.code == "NO_ACTIVE_RULE"


def test_resubmitting_creates_a_second_distinct_row_leaving_the_first_unchanged(
    db_session: Session,
) -> None:
    _publish_rule(db_session)
    customer_id = _seed_customer(db_session, "risk.customer5@wealthwise.test")

    first = submit_risk_profile(
        db_session,
        customer_id=customer_id,
        answers=ALL_LOW_ANSWERS,
        actor_id=customer_id,
        actor_role="customer",
    )
    db_session.commit()
    all_high = {f"Q{i}": "high" for i in range(1, 7)}
    second = submit_risk_profile(
        db_session,
        customer_id=customer_id,
        answers=all_high,
        actor_id=customer_id,
        actor_role="customer",
    )
    db_session.commit()

    assert first.id != second.id
    assert first.risk_band == "CONSERVATIVE"
    assert second.risk_band == "AGGRESSIVE"

    from src.domain.risk_profile.repository import get_latest_assignment

    latest = get_latest_assignment(db_session, customer_id)
    assert latest is not None
    assert latest.id == second.id
    # the first row is untouched
    assert first.risk_band == "CONSERVATIVE"


def test_get_active_questionnaire_returns_the_full_active_rule_including_points(
    db_session: Session,
) -> None:
    _publish_rule(db_session)

    rule = get_active_questionnaire(db_session)

    assert rule is not None
    assert rule.version == 1
    assert rule.questionnaire_json.questions[0].options[0].points == 1


def test_get_active_questionnaire_returns_none_when_never_published(
    db_session: Session,
) -> None:
    assert get_active_questionnaire(db_session) is None
