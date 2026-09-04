"""`domain/audit/service.py` — write_audit_entry() (E3-S2 AC1-AC5)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_user

from src.domain.audit import service as audit_service
from src.domain.audit.repository import query_audit_entries
from src.domain.auth.repository import create_user
from src.types.errors import ValidationError


def _seed_actor(session: Session, *, role: str = "advisor") -> int:
    seed = build_user(email=f"audit.actor.{role}@wealthwise.test", role=role)
    user = create_user(
        session,
        email=seed.email,
        password_hash=seed.password_hash,
        role=seed.role,
        created_at=seed.created_at,
    )
    session.commit()
    return user.id


def test_valid_call_produces_exactly_one_new_row(db_session: Session) -> None:
    actor_id = _seed_actor(db_session)

    entry = audit_service.write_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="7",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        details={"customer_id": 7, "risk_band": "MODERATE", "rule_version": 1},
    )
    db_session.commit()

    rows = query_audit_entries(
        db_session,
        entity_type="RiskBandAssignment",
        start="2000-01-01T00:00:00Z",
        end="2999-01-01T00:00:00Z",
    )
    assert len(rows) == 1
    assert rows[0].id == entry.id
    assert rows[0].entity_id == "7"


@pytest.mark.parametrize("bad_role", [None, "", "superadmin", "customer_service"])
def test_rejects_a_call_missing_actor_role_or_with_an_unknown_actor_role(
    db_session: Session, bad_role: str | None
) -> None:
    actor_id = _seed_actor(db_session)

    with pytest.raises(ValidationError):
        audit_service.write_audit_entry(
            db_session,
            entity_type="RiskBandAssignment",
            entity_id="7",
            actor_id=actor_id,
            actor_role=bad_role,  # type: ignore[arg-type]
            action="ASSIGN_RISK_BAND",
            details={"customer_id": 7},
        )

    rows = query_audit_entries(
        db_session,
        entity_type="RiskBandAssignment",
        start="2000-01-01T00:00:00Z",
        end="2999-01-01T00:00:00Z",
    )
    assert rows == []


def test_a_downstream_flow_risk_band_assignment_invokes_the_audit_writer_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor_id = _seed_actor(db_session, role="admin")
    spy = MagicMock(wraps=audit_service.write_audit_entry)
    monkeypatch.setattr(audit_service, "write_audit_entry", spy)

    def _assign_risk_band_and_audit(session: Session, *, customer_id: int) -> None:
        """A stand-in for the future risk-band-scoring service (E4-S2, group E):
        it must call the audit-writer exactly once per assignment."""
        audit_service.write_audit_entry(
            session,
            entity_type="RiskBandAssignment",
            entity_id=str(customer_id),
            actor_id=actor_id,
            actor_role="admin",
            action="ASSIGN_RISK_BAND",
            details={"customer_id": customer_id, "risk_band": "MODERATE", "rule_version": 1},
        )

    _assign_risk_band_and_audit(db_session, customer_id=42)
    db_session.commit()

    spy.assert_called_once()


def test_failures_inside_the_repository_propagate_rather_than_being_swallowed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated repository failure")

    monkeypatch.setattr(audit_service, "insert_audit_entry", _boom)

    with pytest.raises(RuntimeError, match="simulated repository failure"):
        audit_service.write_audit_entry(
            db_session,
            entity_type="RiskBandAssignment",
            entity_id="1",
            actor_id=1,
            actor_role="advisor",
            action="ASSIGN_RISK_BAND",
            details={"customer_id": 1},
        )


def test_calling_twice_never_overwrites_the_prior_entry_both_rows_persist(
    db_session: Session,
) -> None:
    actor_id = _seed_actor(db_session)

    first = audit_service.write_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="7",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        details={"customer_id": 7, "risk_band": "MODERATE", "rule_version": 1},
    )
    db_session.commit()
    second = audit_service.write_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="7",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        details={"customer_id": 7, "risk_band": "AGGRESSIVE", "rule_version": 1},
    )
    db_session.commit()

    assert first.id != second.id
    rows = query_audit_entries(
        db_session,
        entity_type="RiskBandAssignment",
        start="2000-01-01T00:00:00Z",
        end="2999-01-01T00:00:00Z",
    )
    assert {row.id for row in rows} == {first.id, second.id}
