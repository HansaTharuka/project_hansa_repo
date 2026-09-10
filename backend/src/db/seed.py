"""Idempotent master-data seed loader (E1-S3 AC2, AC3; E5-S1 AC5, ut-067; E8-S1
ut-090; data-models.md §7).

Reads `backend/seed/demo_accounts.json` and inserts: 8–10 customer users (each
paired 1:1 with a `Customer` row), 2 advisors, 1 admin, 1 compliance user; 5–6
`AssetClass` rows; one `RiskBandAssignment` row per customer at `rule_version =
1`, spanning all three risk bands (component-map.md note 2); 6 `AllocationTemplate`
rows (2 published versions for each of CONSERVATIVE, MODERATE, AGGRESSIVE, newest
active — E5-S1 AC5); and exactly one `RebalancingThreshold` row (version 1,
`threshold_bps` derived from `core.config.Settings.default_drift_threshold_percent`,
never a hardcoded literal here — E8-S1, component-map.md's E8-S1 row, ut-090).
`User` and `Customer` are written through the ORM (`db/models.py`); `AssetClass`
and `RiskBandAssignment` are written through parameterized `text()` statements
because their `Mapped` classes belong to later repository stories (E6-S1, E4-S1 —
see `db/models.py`'s module docstring); `AllocationTemplate` and
`RebalancingThreshold` are written through their own repositories' `publish_*`
functions so the insert-only-versioned invariants (allocation-sum, bps range) are
enforced identically to any other caller. Every step is idempotent: re-running
creates no duplicate rows.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import bcrypt
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.db.models import Customer, User
from src.domain.rebalancing.threshold_repository import get_active_threshold, publish_threshold
from src.domain.recommendation.repository import get_active_template, publish_template
from src.types.entities import AllocationEntry, AllocationSet

DEMO_ACCOUNTS_PATH = Path(__file__).resolve().parents[2] / "seed" / "demo_accounts.json"
SYNTHETIC_PASSWORD = "WealthWise-Demo-Synthetic-2026!"  # pragma: allowlist secret
BCRYPT_COST_FACTOR = 12
SEEDED_RULE_VERSION = 1

# One seed `AllocationSet` per risk band (asset-class codes from demo_accounts.json's
# `asset_classes` list), each summing to exactly 10000 bps (AC-02, NFR-08). Published
# twice per band (component-map.md's E5-S1 row: "2 versions per band") so the newer
# version is the active one and the older stays queryable, matching the same
# insert-only-versioned pattern already used for `RiskBandRule`.
SEED_ALLOCATIONS_BY_BAND: dict[str, dict[str, int]] = {
    "CONSERVATIVE": {"FI_GOV": 4000, "FI_CORP": 3000, "CASH": 2000, "EQ_DM": 1000},
    "MODERATE": {
        "EQ_DM": 3000,
        "EQ_EM": 1000,
        "FI_GOV": 2500,
        "FI_CORP": 2000,
        "CASH": 1000,
        "RE": 500,
    },
    "AGGRESSIVE": {
        "EQ_DM": 4500,
        "EQ_EM": 2500,
        "FI_GOV": 1000,
        "FI_CORP": 500,
        "CASH": 500,
        "RE": 1000,
    },
}
ALLOCATION_TEMPLATE_VERSIONS_PER_BAND = 2


class AccountSeed(TypedDict):
    email: str


class CustomerSeed(TypedDict):
    email: str
    kyc_verified: bool
    risk_band: str


class AssetClassSeed(TypedDict):
    code: str
    name: str


class DemoAccounts(TypedDict):
    customers: list[CustomerSeed]
    advisors: list[AccountSeed]
    admins: list[AccountSeed]
    compliance: list[AccountSeed]
    asset_classes: list[AssetClassSeed]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_demo_accounts(path: Path = DEMO_ACCOUNTS_PATH) -> DemoAccounts:
    """Parse the authored seed source (`backend/seed/demo_accounts.json`)."""
    with path.open(encoding="utf-8") as handle:
        data: DemoAccounts = json.load(handle)
    return data


def hash_synthetic_password() -> str:
    """One bcrypt hash (cost 12) reused across every seeded account (Synthetic-Data)."""
    hashed = bcrypt.hashpw(
        SYNTHETIC_PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST_FACTOR)
    )
    return hashed.decode("utf-8")


def _get_or_create_user(session: Session, *, email: str, role: str, password_hash: str) -> User:
    existing = session.query(User).filter(User.email == email.lower()).one_or_none()
    if existing is not None:
        return existing
    user = User(email=email.lower(), password_hash=password_hash, role=role, created_at=_now_iso())
    session.add(user)
    session.flush()
    return user


def _get_or_create_customer(session: Session, *, user_id: int, kyc_verified: bool) -> Customer:
    existing = session.query(Customer).filter(Customer.user_id == user_id).one_or_none()
    if existing is not None:
        return existing
    customer = Customer(user_id=user_id, kyc_verified=kyc_verified, created_at=_now_iso())
    session.add(customer)
    session.flush()
    return customer


def _seed_asset_classes(session: Session, asset_classes: list[AssetClassSeed]) -> None:
    for asset_class in asset_classes:
        existing = session.execute(
            text("SELECT id FROM asset_class WHERE code = :code"),
            {"code": asset_class["code"]},
        ).one_or_none()
        if existing is not None:
            continue
        session.execute(
            text("INSERT INTO asset_class (code, name) VALUES (:code, :name)"),
            {"code": asset_class["code"], "name": asset_class["name"]},
        )


def _seed_risk_band_assignment(session: Session, *, customer_id: int, risk_band: str) -> None:
    existing = session.execute(
        text("SELECT id FROM risk_band_assignment WHERE customer_id = :customer_id"),
        {"customer_id": customer_id},
    ).one_or_none()
    if existing is not None:
        return
    session.execute(
        text(
            "INSERT INTO risk_band_assignment "
            "(customer_id, risk_band, rule_version, assigned_at) "
            "VALUES (:customer_id, :risk_band, :rule_version, :assigned_at)"
        ),
        {
            "customer_id": customer_id,
            "risk_band": risk_band,
            "rule_version": SEEDED_RULE_VERSION,
            "assigned_at": _now_iso(),
        },
    )


def _seed_staff_users(session: Session, demo_accounts: DemoAccounts, password_hash: str) -> None:
    for advisor in demo_accounts["advisors"]:
        _get_or_create_user(
            session, email=advisor["email"], role="advisor", password_hash=password_hash
        )
    for admin in demo_accounts["admins"]:
        _get_or_create_user(
            session, email=admin["email"], role="admin", password_hash=password_hash
        )
    for compliance in demo_accounts["compliance"]:
        _get_or_create_user(
            session, email=compliance["email"], role="compliance", password_hash=password_hash
        )


def _seed_customers(session: Session, demo_accounts: DemoAccounts, password_hash: str) -> None:
    for customer_seed in demo_accounts["customers"]:
        user = _get_or_create_user(
            session, email=customer_seed["email"], role="customer", password_hash=password_hash
        )
        customer = _get_or_create_customer(
            session, user_id=user.id, kyc_verified=customer_seed["kyc_verified"]
        )
        _seed_risk_band_assignment(
            session, customer_id=customer.id, risk_band=customer_seed["risk_band"]
        )


def _asset_class_ids(session: Session) -> dict[str, int]:
    rows = session.execute(text("SELECT code, id FROM asset_class")).all()
    return {code: asset_class_id for code, asset_class_id in rows}


def _seed_allocation_templates(session: Session) -> None:
    """Two published versions per risk band, six rows total (E5-S1 AC5, ut-067)."""
    asset_class_ids = _asset_class_ids(session)
    for risk_band, weights in SEED_ALLOCATIONS_BY_BAND.items():
        if get_active_template(session, risk_band) is not None:
            continue
        allocations = AllocationSet(
            allocations=[
                AllocationEntry(asset_class_id=asset_class_ids[code], percent_bps=percent_bps)
                for code, percent_bps in weights.items()
            ]
        )
        for _ in range(ALLOCATION_TEMPLATE_VERSIONS_PER_BAND):
            publish_template(
                session, risk_band=risk_band, allocations=allocations, published_at=_now_iso()
            )


def _seed_rebalancing_threshold(session: Session, *, threshold_bps: int) -> None:
    """Exactly one `RebalancingThreshold` row: version 1 (E8-S1, ut-090)."""
    if get_active_threshold(session) is not None:
        return
    publish_threshold(session, threshold_bps=threshold_bps, published_at=_now_iso())


def seed_database(session: Session, demo_accounts_path: Path = DEMO_ACCOUNTS_PATH) -> None:
    """Idempotently seed users, customers, asset classes, risk-band assignments,
    allocation templates and the rebalancing threshold."""
    demo_accounts = load_demo_accounts(demo_accounts_path)
    password_hash = hash_synthetic_password()
    settings = Settings()

    _seed_staff_users(session, demo_accounts, password_hash)
    _seed_customers(session, demo_accounts, password_hash)
    _seed_asset_classes(session, demo_accounts["asset_classes"])
    _seed_allocation_templates(session)
    _seed_rebalancing_threshold(
        session, threshold_bps=settings.default_drift_threshold_percent * 100
    )

    session.commit()
