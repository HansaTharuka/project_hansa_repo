"""NFR-02 — insert-only repositories expose no `update_*`/`delete_*` callables.

Created by E3-S1 for `domain/audit/repository.py` (AuditLogEntry). Extended by
E9-S1 for `domain/advisor/repository.py` (AdvisorOverride) — component-map.md's
E9-S1 row lists this module explicitly. Scoped to exactly these two modules per
sprint-contracts/C.json's architecture_checks.append_only resolution: the other
five repository stories in this group each assert their own append-only-ness in
their own repository test file (RiskBandRule/AllocationTemplate/RebalancingThreshold
are insert-only-*versioned*, not bare-append-only; Goal is genuinely mutable;
AssetClass/Holding are mutable master/current-position data).

Extended again by E10-S1 (AC3): the three versioned-publish modules
(RiskBandRule, AllocationTemplate, RebalancingThreshold) must never grow an
`update_*` function that could mutate `questionnaire_json`/
`scoring_rules_json`/`allocations_json` on an already-published row — a
correction is always a new version, never an in-place edit.
"""

from __future__ import annotations

import src.domain.advisor.repository as advisor_repository
import src.domain.audit.repository as audit_repository
import src.domain.rebalancing.threshold_repository as threshold_repository
import src.domain.recommendation.repository as recommendation_repository
import src.domain.risk_profile.repository as risk_profile_repository


def _public_callables(module: object) -> list[str]:
    return [
        name
        for name in dir(module)
        if not name.startswith("_") and callable(getattr(module, name))
    ]


def test_audit_repository_exposes_no_update_or_delete_function() -> None:
    names = _public_callables(audit_repository)
    assert not any(name.startswith("update_") for name in names)
    assert not any(name.startswith("delete_") for name in names)
    assert getattr(audit_repository, "update_audit_entry", None) is None
    assert getattr(audit_repository, "delete_audit_entry", None) is None


def test_advisor_override_repository_exposes_no_update_or_delete_function() -> None:
    names = _public_callables(advisor_repository)
    assert not any(name.startswith("update_") for name in names)
    assert not any(name.startswith("delete_") for name in names)
    assert getattr(advisor_repository, "update_advisor_override", None) is None
    assert getattr(advisor_repository, "delete_advisor_override", None) is None


def test_risk_band_rule_repository_exposes_no_update_or_delete_function() -> None:
    """E10-S1 AC3: a correction is always a new `RiskBandRule` version."""
    names = _public_callables(risk_profile_repository)
    assert not any(name.startswith("update_") for name in names)
    assert not any(name.startswith("delete_") for name in names)


def test_allocation_template_repository_exposes_no_update_or_delete_function() -> None:
    """E10-S1 AC3: a correction is always a new `AllocationTemplate` version."""
    names = _public_callables(recommendation_repository)
    assert not any(name.startswith("update_") for name in names)
    assert not any(name.startswith("delete_") for name in names)


def test_rebalancing_threshold_repository_exposes_no_update_or_delete_function() -> None:
    """E10-S1 AC3: a correction is always a new `RebalancingThreshold` version."""
    names = _public_callables(threshold_repository)
    assert not any(name.startswith("update_") for name in names)
    assert not any(name.startswith("delete_") for name in names)
