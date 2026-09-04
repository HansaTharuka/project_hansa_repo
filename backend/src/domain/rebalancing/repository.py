"""RebalancingRecommendation persistence — insert plus a one-shot status
transition (E8-S1 AC1-AC5).

No hard-delete function exists anywhere in this module (AC3). `status` only ever
transitions `pending -> accepted` or `pending -> dismissed`, exactly once; a second
transition attempt on an already-resolved row raises `AlreadyResolvedError` and
leaves the row untouched (AC4).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import RebalancingRecommendation as RebalancingRecommendationRow
from src.types.entities import ProposedActions
from src.types.entities import RebalancingRecommendation as RebalancingRecommendationEntity

PENDING = "pending"
ACCEPTED = "accepted"
DISMISSED = "dismissed"


class AlreadyResolvedError(RuntimeError):
    """Raised when a second accept/dismiss transition targets a resolved row."""

    def __init__(self, recommendation_id: str, current_status: str) -> None:
        self.recommendation_id = recommendation_id
        self.current_status = current_status
        super().__init__(
            f"RebalancingRecommendation {recommendation_id!r} is already "
            f"{current_status!r} and cannot be transitioned again."
        )


def insert_recommendation(
    session: Session,
    *,
    customer_id: int,
    recommendation_id: str,
    proposed_actions: ProposedActions,
    generated_at: str,
) -> RebalancingRecommendationEntity:
    """Insert one `pending` `RebalancingRecommendation` row."""
    row = RebalancingRecommendationRow(
        customer_id=customer_id,
        recommendation_id=recommendation_id,
        proposed_actions_json=proposed_actions.model_dump_json(),
        status=PENDING,
        generated_at=generated_at,
        resolved_at=None,
    )
    session.add(row)
    session.flush()
    return _to_entity(row)


def get_by_recommendation_id(
    session: Session, recommendation_id: str
) -> RebalancingRecommendationEntity | None:
    """Look up a recommendation by its public UUID."""
    statement = select(RebalancingRecommendationRow).where(
        RebalancingRecommendationRow.recommendation_id == recommendation_id
    )
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def get_pending(session: Session, customer_id: int) -> list[RebalancingRecommendationEntity]:
    """Only `pending` rows for `customer_id`."""
    statement = select(RebalancingRecommendationRow).where(
        RebalancingRecommendationRow.customer_id == customer_id,
        RebalancingRecommendationRow.status == PENDING,
    )
    rows = session.execute(statement).scalars().all()
    return [_to_entity(row) for row in rows]


def accept(
    session: Session, *, recommendation_id: str, resolved_at: str
) -> RebalancingRecommendationEntity:
    """Transition `pending -> accepted`, once."""
    return _transition(
        session, recommendation_id=recommendation_id, new_status=ACCEPTED, resolved_at=resolved_at
    )


def dismiss(
    session: Session, *, recommendation_id: str, resolved_at: str
) -> RebalancingRecommendationEntity:
    """Transition `pending -> dismissed`, once."""
    return _transition(
        session,
        recommendation_id=recommendation_id,
        new_status=DISMISSED,
        resolved_at=resolved_at,
    )


def _transition(
    session: Session, *, recommendation_id: str, new_status: str, resolved_at: str
) -> RebalancingRecommendationEntity:
    statement = select(RebalancingRecommendationRow).where(
        RebalancingRecommendationRow.recommendation_id == recommendation_id
    )
    row = session.execute(statement).scalar_one()
    if row.status != PENDING:
        raise AlreadyResolvedError(recommendation_id, row.status)
    row.status = new_status
    row.resolved_at = resolved_at
    session.flush()
    return _to_entity(row)


def _to_entity(row: RebalancingRecommendationRow) -> RebalancingRecommendationEntity:
    return RebalancingRecommendationEntity(
        id=row.id,
        customer_id=row.customer_id,
        recommendation_id=row.recommendation_id,
        proposed_actions_json=ProposedActions.model_validate_json(row.proposed_actions_json),
        status=row.status,  # type: ignore[arg-type]
        generated_at=row.generated_at,
        resolved_at=row.resolved_at,
    )
