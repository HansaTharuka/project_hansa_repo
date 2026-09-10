"""Seed-loader tests (E1-S3 AC2, AC3; ut-035, ut-036, ut-038, ut-042; data-models.md §7)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.seed import seed_database

EXPECTED_RISK_BANDS = {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"}


def _count(session: Session, sql: str, params: dict[str, object] | None = None) -> int:
    return session.execute(text(sql), params or {}).scalar_one()


def test_seed_creates_customer_users_paired_one_to_one_with_customer_rows(
    seeded_session: Session,
) -> None:
    customer_user_count = _count(
        seeded_session, "SELECT COUNT(*) FROM user WHERE role = 'customer'"
    )
    assert 8 <= customer_user_count <= 10

    orphan_customers = _count(
        seeded_session,
        "SELECT COUNT(*) FROM customer c "
        "LEFT JOIN user u ON u.id = c.user_id AND u.role = 'customer' "
        "WHERE u.id IS NULL",
    )
    assert orphan_customers == 0

    customer_rows_without_user = customer_user_count - _count(
        seeded_session,
        "SELECT COUNT(*) FROM user u JOIN customer c ON c.user_id = u.id "
        "WHERE u.role = 'customer'",
    )
    assert customer_rows_without_user == 0


def test_seed_creates_exactly_the_documented_staff_role_counts(seeded_session: Session) -> None:
    assert _count(seeded_session, "SELECT COUNT(*) FROM user WHERE role = 'advisor'") == 2
    assert _count(seeded_session, "SELECT COUNT(*) FROM user WHERE role = 'admin'") == 1
    assert _count(seeded_session, "SELECT COUNT(*) FROM user WHERE role = 'compliance'") == 1


def test_seed_creates_five_to_six_asset_classes_with_distinct_codes(
    seeded_session: Session,
) -> None:
    total = _count(seeded_session, "SELECT COUNT(*) FROM asset_class")
    distinct_codes = _count(seeded_session, "SELECT COUNT(DISTINCT code) FROM asset_class")
    assert 5 <= total <= 6
    assert distinct_codes == total
    empty_codes = _count(
        seeded_session, "SELECT COUNT(*) FROM asset_class WHERE code IS NULL OR code = ''"
    )
    assert empty_codes == 0


def test_seed_creates_unique_lowercase_emails(seeded_session: Session) -> None:
    total_users = _count(seeded_session, "SELECT COUNT(*) FROM user")
    distinct_lower_emails = _count(seeded_session, "SELECT COUNT(DISTINCT LOWER(email)) FROM user")
    non_lowercase = _count(seeded_session, "SELECT COUNT(*) FROM user WHERE email != LOWER(email)")
    assert distinct_lower_emails == total_users
    assert non_lowercase == 0


def test_seed_assigns_exactly_one_risk_band_row_per_customer_at_rule_version_one(
    seeded_session: Session,
) -> None:
    customer_count = _count(seeded_session, "SELECT COUNT(*) FROM customer")
    assignment_count = _count(seeded_session, "SELECT COUNT(*) FROM risk_band_assignment")
    assert assignment_count == customer_count

    customers_with_exactly_one = _count(
        seeded_session,
        "SELECT COUNT(*) FROM ("
        "  SELECT customer_id FROM risk_band_assignment "
        "  GROUP BY customer_id HAVING COUNT(*) = 1"
        ") AS one_per_customer",
    )
    assert customers_with_exactly_one == customer_count

    wrong_rule_version = _count(
        seeded_session, "SELECT COUNT(*) FROM risk_band_assignment WHERE rule_version != 1"
    )
    assert wrong_rule_version == 0


def test_seed_assigns_all_three_risk_bands_across_customers(seeded_session: Session) -> None:
    rows = seeded_session.execute(text("SELECT DISTINCT risk_band FROM risk_band_assignment")).all()
    bands = {row[0] for row in rows}
    assert bands == EXPECTED_RISK_BANDS


def test_seed_leaves_at_least_one_customer_kyc_unverified_and_the_rest_verified(
    seeded_session: Session,
) -> None:
    verified = _count(seeded_session, "SELECT COUNT(*) FROM customer WHERE kyc_verified = 1")
    unverified = _count(seeded_session, "SELECT COUNT(*) FROM customer WHERE kyc_verified = 0")
    total = _count(seeded_session, "SELECT COUNT(*) FROM customer")
    assert verified > 0
    assert unverified > 0
    assert verified + unverified == total


def test_seed_is_idempotent_on_a_second_run(seeded_session: Session) -> None:
    before_users = _count(seeded_session, "SELECT COUNT(*) FROM user")
    before_asset_classes = _count(seeded_session, "SELECT COUNT(*) FROM asset_class")
    before_assignments = _count(seeded_session, "SELECT COUNT(*) FROM risk_band_assignment")

    seed_database(seeded_session)

    after_users = _count(seeded_session, "SELECT COUNT(*) FROM user")
    after_asset_classes = _count(seeded_session, "SELECT COUNT(*) FROM asset_class")
    after_assignments = _count(seeded_session, "SELECT COUNT(*) FROM risk_band_assignment")

    assert after_users == before_users
    assert after_asset_classes == before_asset_classes
    assert after_assignments == before_assignments
