"""Admin repository cross-cutting tests (E10-S1 AC2, AC4).

AC1, AC3, AC5 are exercised by each owning module's own test file
(`test_risk_profile_repository.py`, `test_allocation_template_repository.py`,
`test_threshold_repository.py`) and by `tests/architecture/test_append_only.py`
— this file covers what is specific to E10-S1: the DB-level monotonic-version
uniqueness guarantee (AC2) and asset-class master CRUD (AC4).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import AllocationTemplate as AllocationTemplateRow
from src.db.models import RebalancingThreshold as RebalancingThresholdRow
from src.db.models import RiskBandRule as RiskBandRuleRow
from src.domain.admin.repository import update_asset_class
from src.domain.holdings.repository import get_asset_class_by_code, insert_asset_class
from src.domain.rebalancing.threshold_repository import publish_threshold
from src.domain.recommendation.repository import get_template_by_version, publish_template
from src.domain.risk_profile.repository import publish_rule
from src.types.entities import (
    AllocationEntry,
    AllocationSet,
    BandRange,
    Question,
    Questionnaire,
    QuestionOption,
    ScoringRules,
)
from src.types.errors import NotFoundError

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


# --- AC2: a second concurrent publish for the same next version number fails
# rather than silently overwriting. Two sequential `publish_*` calls can never
# collide (each freshly computes `max(version) + 1`, per system-design.md
# §9.5) — a genuine race is two writers computing the identical next version
# from the same stale read, which is reproduced deterministically here by
# inserting a duplicate row directly rather than depending on timing.


def test_a_duplicate_risk_band_rule_version_is_rejected_by_the_unique_index(
    db_session: Session,
) -> None:
    publish_rule(
        db_session, questionnaire=QUESTIONNAIRE, scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    colliding = RiskBandRuleRow(
        version=1,
        questionnaire_json=QUESTIONNAIRE.model_dump_json(),
        scoring_rules_json=SCORING_RULES.model_dump_json(),
        published_at="2026-09-01T09:05:00Z",
        is_active=True,
    )
    db_session.add(colliding)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_a_duplicate_allocation_template_band_version_is_rejected_by_the_unique_index(
    db_session: Session,
) -> None:
    asset_class = insert_asset_class(db_session, code="EQ_TEST", name="Test Equity")
    db_session.commit()
    publish_template(
        db_session,
        risk_band="MODERATE",
        allocations=AllocationSet(
            allocations=[AllocationEntry(asset_class_id=asset_class.id, percent_bps=10000)]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    colliding = AllocationTemplateRow(
        version=1,
        risk_band="MODERATE",
        allocations_json=AllocationSet(
            allocations=[AllocationEntry(asset_class_id=asset_class.id, percent_bps=10000)]
        ).model_dump_json(),
        published_at="2026-09-01T09:05:00Z",
        is_active=True,
    )
    db_session.add(colliding)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_a_duplicate_rebalancing_threshold_version_is_rejected_by_the_unique_index(
    db_session: Session,
) -> None:
    publish_threshold(db_session, threshold_bps=500, published_at="2026-09-01T09:00:00Z")
    db_session.commit()

    colliding = RebalancingThresholdRow(
        version=1, threshold_bps=700, published_at="2026-09-01T09:05:00Z", is_active=True
    )
    db_session.add(colliding)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# --- AC4: asset-class master CRUD.


def test_updating_code_and_name_persists_and_is_reflected_on_the_next_read(
    db_session: Session,
) -> None:
    asset_class = insert_asset_class(db_session, code="OLD_CODE", name="Old Name")
    db_session.commit()

    updated = update_asset_class(
        db_session, asset_class_id=asset_class.id, code="NEW_CODE", name="New Name"
    )
    db_session.commit()

    assert updated.code == "NEW_CODE"
    assert updated.name == "New Name"
    assert get_asset_class_by_code(db_session, "NEW_CODE") is not None
    assert get_asset_class_by_code(db_session, "OLD_CODE") is None


def test_updating_only_the_name_leaves_the_code_unchanged(db_session: Session) -> None:
    asset_class = insert_asset_class(db_session, code="STABLE_CODE", name="Original Name")
    db_session.commit()

    updated = update_asset_class(db_session, asset_class_id=asset_class.id, name="Renamed")

    assert updated.code == "STABLE_CODE"
    assert updated.name == "Renamed"


def test_updating_a_nonexistent_asset_class_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        update_asset_class(db_session, asset_class_id=999_999, name="Nobody Here")

    assert excinfo.value.code == "ASSET_CLASS_NOT_FOUND"


def test_updating_an_asset_class_to_a_duplicate_code_fails_via_the_unique_index(
    db_session: Session,
) -> None:
    insert_asset_class(db_session, code="TAKEN_CODE", name="First")
    second = insert_asset_class(db_session, code="OTHER_CODE", name="Second")
    db_session.commit()

    with pytest.raises(IntegrityError):
        update_asset_class(db_session, asset_class_id=second.id, code="TAKEN_CODE")
    db_session.rollback()


def test_renaming_an_asset_class_does_not_affect_a_published_template_referencing_it(
    db_session: Session,
) -> None:
    asset_class = insert_asset_class(db_session, code="EQ_RENAME", name="Before Rename")
    db_session.commit()
    template = publish_template(
        db_session,
        risk_band="AGGRESSIVE",
        allocations=AllocationSet(
            allocations=[AllocationEntry(asset_class_id=asset_class.id, percent_bps=10000)]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    update_asset_class(
        db_session, asset_class_id=asset_class.id, code="EQ_RENAMED", name="After Rename"
    )
    db_session.commit()

    reread = get_template_by_version(db_session, risk_band="AGGRESSIVE", version=template.version)
    assert reread is not None
    assert reread.allocations_json.allocations[0].asset_class_id == asset_class.id
    assert reread.allocations_json.allocations[0].percent_bps == 10000
