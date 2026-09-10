"""Admin-facing repository operations that cut across the versioned-publish
tables and asset-class master data (E10-S1).

AC1, AC2, AC3, AC5 are already fully delivered by the versioned-publish
pattern each owning module implements: `risk_profile.repository.publish_rule`,
`recommendation.repository.publish_template`, and
`rebalancing.threshold_repository.publish_threshold` each compute
`next_version = max(existing_version) + 1`, flip the prior active row's
`is_active` to `False`, and insert the new version — never an in-place edit
of `questionnaire_json`/`scoring_rules_json`/`allocations_json` (no
`update_rule`/`update_template`/`update_threshold` function exists anywhere,
`tests/architecture/test_append_only.py`). The uniqueness indexes backing
AC2 (`ix_rbr_version`, `ix_at_band_version`, `ix_rt_version`) are DB-level
guarantees, not a check-then-act read — a genuine concurrent publish race
loses on `IntegrityError` at insert, the same "fail loud, never overwrite"
guarantee `holdings.service.advance_day` relies on for `NavSnapshot`
(system-design.md §9.5).

What was missing, and what this module adds, is AC4: `AssetClass` is master
data, not a versioned-publish table — `code`/`name` are edited in place, and
because `AllocationTemplate.allocations_json` references `asset_class_id`
only inside its JSON document (never a database foreign key,
data-models.md §4.9), renaming or recoding an asset class can never rewrite
a published template. `insert_asset_class` (the "create" half of AC4)
already exists in `holdings.repository` (E6-S1) — this module adds only the
"update" half, the one operation genuinely missing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AssetClass as AssetClassRow
from src.types.entities import AssetClass as AssetClassEntity
from src.types.errors import NotFoundError


def update_asset_class(
    session: Session,
    *,
    asset_class_id: int,
    code: str | None = None,
    name: str | None = None,
) -> AssetClassEntity:
    """Edit `code` and/or `name` of an existing `AssetClass` row in place
    (AC4). A duplicate `code` fails on the `ix_ac_code` unique index rather
    than silently colliding with another asset class — the same DB-level
    guarantee `data-models.md` §4.9 documents for a duplicate insert.

    Never touches any `AllocationTemplate` row: templates reference
    `asset_class_id`, an id that never changes, so a historical template
    still resolves correctly through the renamed/recoded row.
    """
    row = session.execute(
        select(AssetClassRow).where(AssetClassRow.id == asset_class_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            f"AssetClass {asset_class_id} does not exist.", code="ASSET_CLASS_NOT_FOUND"
        )
    if code is not None:
        row.code = code
    if name is not None:
        row.name = name
    session.flush()
    return _to_entity(row)


def _to_entity(row: AssetClassRow) -> AssetClassEntity:
    return AssetClassEntity(id=row.id, code=row.code, name=row.name)
