"""`domain/risk_profile/repository.py` tests (E4-S1 AC1-AC5; ut-058..ut-062)."""

from __future__ import annotations

from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.domain.auth.repository import create_user
from src.domain.risk_profile.repository import (
    get_active_rule,
    get_rule_by_version,
    insert_answers,
    publish_rule,
)
from src.types.entities import BandRange, Question, Questionnaire, QuestionOption, ScoringRules

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


def _seed_customer(session: Session) -> int:
    user_seed = build_user(email="risk.customer@wealthwise.test")
    user = create_user(
        session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    from src.db.models import Customer

    customer_seed = build_customer(user_id=user.id)
    customer = Customer(
        user_id=customer_seed.user_id,
        kyc_verified=customer_seed.kyc_verified,
        created_at=customer_seed.created_at,
    )
    session.add(customer)
    session.commit()
    return customer.id


def test_publish_rule_round_trips_version_one_with_at_least_six_questions(
    db_session: Session,
) -> None:
    rule = publish_rule(
        db_session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    assert rule.version == 1
    assert rule.is_active is True
    assert len(rule.questionnaire_json.questions) >= 6
    assert rule.scoring_rules_json == SCORING_RULES
    assert rule.published_at == "2026-09-01T09:00:00Z"


def test_repository_exposes_no_update_function_for_risk_band_rule() -> None:
    import src.domain.risk_profile.repository as repository_module

    assert getattr(repository_module, "update_rule", None) is None
    assert getattr(repository_module, "update_risk_band_rule", None) is None


def test_get_active_rule_returns_exactly_one_row_the_newest(db_session: Session) -> None:
    publish_rule(
        db_session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()
    publish_rule(
        db_session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-02T09:00:00Z",
    )
    db_session.commit()

    active = get_active_rule(db_session)

    assert active is not None
    assert active.version == 2
    assert active.is_active is True


def test_repository_exposes_no_update_or_delete_function_for_risk_profile_answer(
) -> None:
    import src.domain.risk_profile.repository as repository_module

    assert getattr(repository_module, "update_answer", None) is None
    assert getattr(repository_module, "delete_answer", None) is None


def test_two_submissions_for_the_same_customer_are_both_queryable(db_session: Session) -> None:
    customer_id = _seed_customer(db_session)

    first = insert_answers(
        db_session,
        customer_id=customer_id,
        answers=[("Q1", "low"), ("Q2", "high")],
        submitted_at="2026-09-01T10:00:00Z",
    )
    db_session.commit()
    second = insert_answers(
        db_session,
        customer_id=customer_id,
        answers=[("Q1", "high"), ("Q2", "low")],
        submitted_at="2026-09-02T10:00:00Z",
    )
    db_session.commit()

    assert len(first) == 2
    assert len(second) == 2
    assert {answer.answer_value for answer in first} == {"low", "high"}
    assert {answer.answer_value for answer in second} == {"low", "high"}


def test_publishing_a_second_version_flips_the_first_versions_is_active_flag(
    db_session: Session,
) -> None:
    publish_rule(
        db_session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()
    publish_rule(
        db_session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-02T09:00:00Z",
    )
    db_session.commit()

    version_one = get_rule_by_version(db_session, 1)

    assert version_one is not None
    assert version_one.is_active is False
    assert len(version_one.questionnaire_json.questions) >= 6


def test_each_risk_profile_answer_row_records_the_documented_fields(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session)

    answers = insert_answers(
        db_session,
        customer_id=customer_id,
        answers=[("Q1", "low")],
        submitted_at="2026-09-03T10:15:00Z",
    )
    db_session.commit()

    assert answers[0].customer_id == customer_id
    assert answers[0].question_id == "Q1"
    assert answers[0].answer_value == "low"
    assert answers[0].submitted_at == "2026-09-03T10:15:00Z"
