"""`domain/audit/repository.py` tests (E3-S1 AC1-AC5; ut-054, ut-055, ut-056, ut-057)."""

from __future__ import annotations

from sqlalchemy.orm import Session
from tests.factories import build_user

from src.domain.audit.repository import count_audit_entries, insert_audit_entry, query_audit_entries
from src.domain.auth.repository import create_user


def _seed_actor(session: Session) -> int:
    seed = build_user(email="advisor.actor@wealthwise.test", role="advisor")
    user = create_user(
        session,
        email=seed.email,
        password_hash=seed.password_hash,
        role=seed.role,
        created_at=seed.created_at,
    )
    session.commit()
    return user.id


def test_insert_audit_entry_round_trips_every_column(db_session: Session) -> None:
    actor_id = _seed_actor(db_session)

    entry = insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="12",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T10:15:00Z",
        details_json={"customer_id": 3, "risk_band": "MODERATE", "rule_version": 1},
    )
    db_session.commit()

    assert entry.entity_type == "RiskBandAssignment"
    assert entry.entity_id == "12"
    assert entry.actor_id == actor_id
    assert entry.actor_role == "advisor"
    assert entry.action == "ASSIGN_RISK_BAND"
    assert entry.timestamp == "2026-09-03T10:15:00Z"
    assert entry.details_json == {"customer_id": 3, "risk_band": "MODERATE", "rule_version": 1}


def test_repository_exposes_no_update_or_delete_function_for_audit_log_entry() -> None:
    import src.domain.audit.repository as repository_module

    for name in dir(repository_module):
        assert not name.startswith("update_"), f"unexpected mutator {name}"
        assert not name.startswith("delete_"), f"unexpected mutator {name}"
    assert getattr(repository_module, "update_audit_entry", None) is None
    assert getattr(repository_module, "delete_audit_entry", None) is None


def test_query_by_entity_type_and_date_range_returns_rows_ordered_by_timestamp_asc(
    db_session: Session,
) -> None:
    actor_id = _seed_actor(db_session)
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="3",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T12:00:00Z",
        details_json={"customer_id": 3},
    )
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="4",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T09:00:00Z",
        details_json={"customer_id": 4},
    )
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="5",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T15:00:00Z",
        details_json={"customer_id": 5},
    )
    # Out of range and out of entity_type — must be excluded.
    insert_audit_entry(
        db_session,
        entity_type="AdvisorOverride",
        entity_id="6",
        actor_id=actor_id,
        actor_role="advisor",
        action="OVERRIDE_RISK_BAND",
        timestamp="2026-09-03T13:00:00Z",
        details_json={"customer_id": 6},
    )
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="7",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-04T09:00:00Z",
        details_json={"customer_id": 7},
    )
    db_session.commit()

    results = query_audit_entries(
        db_session,
        entity_type="RiskBandAssignment",
        start="2026-09-03T00:00:00Z",
        end="2026-09-03T23:59:59Z",
    )

    assert [entry.entity_id for entry in results] == ["4", "3", "5"]


def test_query_and_count_by_bare_end_date_includes_entries_timestamped_later_that_day(
    db_session: Session,
) -> None:
    """A bare `YYYY-MM-DD` `end` boundary (as sent by the frontend's `<input
    type="date">` filter, E3-S4 AC3) must be treated as inclusive of the
    whole day, not as an exclusive midnight cutoff (api-contracts.md §13.1)."""
    actor_id = _seed_actor(db_session)
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="20",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T15:00:00Z",
        details_json={"customer_id": 20},
    )
    # The day after the `end` boundary — must stay excluded.
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="21",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-04T00:00:01Z",
        details_json={"customer_id": 21},
    )
    db_session.commit()

    results = query_audit_entries(db_session, end="2026-09-03")
    total = count_audit_entries(db_session, end="2026-09-03")

    assert [entry.entity_id for entry in results] == ["20"]
    assert total == 1


def test_query_by_full_timestamp_end_is_not_double_expanded(db_session: Session) -> None:
    """An `end` that already carries a time component must be used exactly
    as given — a bare-date expansion must not also be applied to it."""
    actor_id = _seed_actor(db_session)
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="30",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T09:00:00Z",
        details_json={"customer_id": 30},
    )
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="31",
        actor_id=actor_id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T15:00:00Z",
        details_json={"customer_id": 31},
    )
    db_session.commit()

    results = query_audit_entries(db_session, end="2026-09-03T10:00:00Z")

    assert [entry.entity_id for entry in results] == ["30"]


def test_query_by_actor_id_returns_only_that_actor_s_entries(db_session: Session) -> None:
    actor_one = _seed_actor(db_session)
    other_seed = build_user(email="advisor.other@wealthwise.test", role="advisor")
    other_actor = create_user(
        db_session,
        email=other_seed.email,
        password_hash=other_seed.password_hash,
        role=other_seed.role,
        created_at=other_seed.created_at,
    )
    db_session.commit()
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="10",
        actor_id=actor_one,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T09:00:00Z",
        details_json={"customer_id": 10},
    )
    insert_audit_entry(
        db_session,
        entity_type="RiskBandAssignment",
        entity_id="11",
        actor_id=other_actor.id,
        actor_role="advisor",
        action="ASSIGN_RISK_BAND",
        timestamp="2026-09-03T10:00:00Z",
        details_json={"customer_id": 11},
    )
    db_session.commit()

    results = query_audit_entries(db_session, actor_id=actor_one)

    assert [entry.entity_id for entry in results] == ["10"]
    assert all(entry.actor_id == actor_one for entry in results)


def test_details_json_fixture_examples_carry_only_ids_enums_and_versions(
    db_session: Session,
) -> None:
    actor_id = _seed_actor(db_session)
    entry = insert_audit_entry(
        db_session,
        entity_type="RiskBandRule",
        entity_id="1",
        actor_id=actor_id,
        actor_role="admin",
        action="PUBLISH_RISK_BAND_RULE",
        timestamp="2026-09-01T09:00:00Z",
        details_json={"customer_id": 3, "risk_band": "MODERATE", "rule_version": 1},
    )
    db_session.commit()

    for value in entry.details_json.values():
        assert isinstance(value, str | int | bool)
        if isinstance(value, str):
            assert "@" not in value  # no raw email/PII smuggled through
