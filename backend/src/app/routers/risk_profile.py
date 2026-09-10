"""POST /api/risk-profile/submit, GET /api/risk-profile/latest — customer-role
risk-profile submission and read (E4-S3 AC1-AC5; api-contracts.md §6.2, §6.3).

`answers` validation for duplicate `question_id`s happens here, at the
request boundary, before `domain.risk_profile.service.submit_risk_profile` is
ever called — a duplicate answer set never reaches the scoring path. This
router calls `domain.risk_profile.service` only, never `domain.risk_profile
.repository` directly (system-design.md D3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.risk_profile.service import (
    get_active_questionnaire,
    get_latest_risk_band_assignment,
    submit_risk_profile,
)
from src.types.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/api/risk-profile", tags=["risk-profile"])


class RiskProfileAnswerRequest(BaseModel):
    """One `(question_id, answer_value)` pair (api-contracts.md §6.2)."""

    question_id: str = Field(min_length=1)
    answer_value: str = Field(min_length=1)


class RiskProfileSubmitRequest(BaseModel):
    """The full submitted answer set — `customer_id` is never part of the body."""

    answers: list[RiskProfileAnswerRequest]


class RiskProfileSubmitResponse(BaseModel):
    """The newly assigned risk band (api-contracts.md §6.2)."""

    assignment_id: int
    risk_band: str
    rule_version: int
    assigned_at: str


class RiskProfileLatestResponse(BaseModel):
    """The customer's most recent `RiskBandAssignment` (api-contracts.md §6.3)."""

    assignment_id: int
    customer_id: int
    risk_band: str
    rule_version: int
    assigned_at: str


class QuestionnaireOptionResponse(BaseModel):
    """One selectable answer — `points` is never included (api-contracts.md
    §6.1: the client must not be able to reverse-engineer the band)."""

    value: str
    label: str


class QuestionnaireQuestionResponse(BaseModel):
    question_id: str
    text: str
    options: list[QuestionnaireOptionResponse]


class QuestionnaireResponse(BaseModel):
    """The active questionnaire, `points`-stripped (api-contracts.md §6.1)."""

    rule_version: int
    questions: list[QuestionnaireQuestionResponse]


@router.post("/submit", status_code=201)
def submit(
    body: RiskProfileSubmitRequest,
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session, scope="function"),
) -> RiskProfileSubmitResponse:
    """Score `body.answers` against the active questionnaire and persist the
    resulting assignment (AC1). An incomplete or malformed answer set raises
    `ValidationError` before any row is written (AC2)."""
    answers = _answers_to_dict(body.answers)
    assignment = submit_risk_profile(
        session,
        customer_id=user.customer_id or 0,
        answers=answers,
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return RiskProfileSubmitResponse(
        assignment_id=assignment.id,
        risk_band=assignment.risk_band,
        rule_version=assignment.rule_version,
        assigned_at=assignment.assigned_at,
    )


@router.get("/latest", status_code=200)
def get_latest(
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session, scope="function"),
) -> RiskProfileLatestResponse:
    """The caller's most recent `RiskBandAssignment` (AC4)."""
    assignment = get_latest_risk_band_assignment(session, user.customer_id or 0)
    if assignment is None:
        raise NotFoundError(
            f"Customer {user.customer_id} has no RiskBandAssignment.",
            code="NO_RISK_BAND_ASSIGNMENT",
        )
    return RiskProfileLatestResponse(
        assignment_id=assignment.id,
        customer_id=assignment.customer_id,
        risk_band=assignment.risk_band,
        rule_version=assignment.rule_version,
        assigned_at=assignment.assigned_at,
    )


@router.get("/questionnaire", status_code=200)
def get_questionnaire(
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session, scope="function"),
) -> QuestionnaireResponse:
    """The active `RiskBandRule`'s questionnaire, with every option's `points`
    stripped so the client can never reverse-engineer the scoring (api-contracts.md
    §6.1). 404 `NO_ACTIVE_RULE` if no rule has ever been published."""
    del user
    rule = get_active_questionnaire(session)
    if rule is None:
        raise NotFoundError("No active RiskBandRule has been published.", code="NO_ACTIVE_RULE")
    return QuestionnaireResponse(
        rule_version=rule.version,
        questions=[
            QuestionnaireQuestionResponse(
                question_id=question.question_id,
                text=question.text,
                options=[
                    QuestionnaireOptionResponse(value=option.value, label=option.label)
                    for option in question.options
                ],
            )
            for question in rule.questionnaire_json.questions
        ],
    )


def _answers_to_dict(answers: list[RiskProfileAnswerRequest]) -> dict[str, str]:
    seen: dict[str, str] = {}
    for answer in answers:
        if answer.question_id in seen:
            raise ValidationError(
                f"Duplicate answer for question {answer.question_id!r}.",
                code="INCOMPLETE_QUESTIONNAIRE",
                details={"duplicate_question_id": answer.question_id},
            )
        seen[answer.question_id] = answer.answer_value
    return seen
