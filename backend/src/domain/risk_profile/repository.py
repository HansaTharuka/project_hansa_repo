"""RiskBandRule / RiskProfileAnswer persistence (E4-S1).

`RiskBandRule` is insert-only and versioned: `publish_rule` computes the next
version, flips the previously active row's `is_active` to `False`, and inserts the
new version as active — the same immutable-versioned-publish pattern used by
`AllocationTemplate` (E5-S1) and `RebalancingThreshold` (E8-S1). No `update_rule`
function exists. `RiskProfileAnswer` is append-only: no `update_*`/`delete_*`
function exists for it either (E4-S1 AC3).

`get_latest_assignment` reads `RiskBandAssignment` — append-only, written by the
future risk-band scoring service (E4-S2, group E) and by advisor overrides
(E9-S2). It is added here, alongside the table's other reader
(`domain.advisor.repository`'s private `_latest_risk_band`), because E6-S3's
drift-recomputation orchestration (`domain.holdings.service.advance_day`, group
D) needs a customer's current risk band to look up their active allocation
template; no other public function exposed it.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import RiskBandAssignment as RiskBandAssignmentRow
from src.db.models import RiskBandRule as RiskBandRuleRow
from src.db.models import RiskProfileAnswer as RiskProfileAnswerRow
from src.types.entities import Questionnaire, ScoringRules
from src.types.entities import RiskBandAssignment as RiskBandAssignmentEntity
from src.types.entities import RiskBandRule as RiskBandRuleEntity
from src.types.entities import RiskProfileAnswer as RiskProfileAnswerEntity


def publish_rule(
    session: Session,
    *,
    questionnaire: Questionnaire,
    scoring_rules: ScoringRules,
    published_at: str,
) -> RiskBandRuleEntity:
    """Insert the next `RiskBandRule` version and deactivate the current one."""
    next_version = _next_version(session)
    _deactivate_current(session)

    row = RiskBandRuleRow(
        version=next_version,
        questionnaire_json=questionnaire.model_dump_json(),
        scoring_rules_json=scoring_rules.model_dump_json(),
        published_at=published_at,
        is_active=True,
    )
    session.add(row)
    session.flush()
    return _to_entity(row)


def get_active_rule(session: Session) -> RiskBandRuleEntity | None:
    """The exactly-one row with `is_active = True`, or `None` if never published."""
    statement = select(RiskBandRuleRow).where(RiskBandRuleRow.is_active.is_(True))
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def get_rule_by_version(session: Session, version: int) -> RiskBandRuleEntity | None:
    """A specific, possibly-superseded rule version — still fully queryable."""
    statement = select(RiskBandRuleRow).where(RiskBandRuleRow.version == version)
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def insert_answers(
    session: Session,
    *,
    customer_id: int,
    answers: list[tuple[str, str]],
    submitted_at: str,
) -> list[RiskProfileAnswerEntity]:
    """Insert one append-only row per (question_id, answer_value) pair."""
    rows = [
        RiskProfileAnswerRow(
            customer_id=customer_id,
            question_id=question_id,
            answer_value=answer_value,
            submitted_at=submitted_at,
        )
        for question_id, answer_value in answers
    ]
    session.add_all(rows)
    session.flush()
    return [_answer_to_entity(row) for row in rows]


def get_latest_assignment(session: Session, customer_id: int) -> RiskBandAssignmentEntity | None:
    """The customer's most recent `RiskBandAssignment`, or `None` if never assigned."""
    statement = (
        select(RiskBandAssignmentRow)
        .where(RiskBandAssignmentRow.customer_id == customer_id)
        .order_by(RiskBandAssignmentRow.assigned_at.desc(), RiskBandAssignmentRow.id.desc())
        .limit(1)
    )
    row = session.execute(statement).scalar_one_or_none()
    return _assignment_to_entity(row) if row is not None else None


def _next_version(session: Session) -> int:
    current_max = session.execute(select(func.max(RiskBandRuleRow.version))).scalar_one()
    return 1 if current_max is None else current_max + 1


def _deactivate_current(session: Session) -> None:
    statement = select(RiskBandRuleRow).where(RiskBandRuleRow.is_active.is_(True))
    active_row = session.execute(statement).scalar_one_or_none()
    if active_row is not None:
        active_row.is_active = False


def _to_entity(row: RiskBandRuleRow) -> RiskBandRuleEntity:
    return RiskBandRuleEntity(
        id=row.id,
        version=row.version,
        questionnaire_json=Questionnaire.model_validate_json(row.questionnaire_json),
        scoring_rules_json=ScoringRules.model_validate_json(row.scoring_rules_json),
        published_at=row.published_at,
        is_active=row.is_active,
    )


def _assignment_to_entity(row: RiskBandAssignmentRow) -> RiskBandAssignmentEntity:
    return RiskBandAssignmentEntity(
        id=row.id,
        customer_id=row.customer_id,
        risk_band=row.risk_band,  # type: ignore[arg-type]
        rule_version=row.rule_version,
        assigned_at=row.assigned_at,
    )


def _answer_to_entity(row: RiskProfileAnswerRow) -> RiskProfileAnswerEntity:
    return RiskProfileAnswerEntity(
        id=row.id,
        customer_id=row.customer_id,
        question_id=row.question_id,
        answer_value=row.answer_value,
        submitted_at=row.submitted_at,
    )
