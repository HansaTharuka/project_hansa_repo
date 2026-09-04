"""SQLAlchemy 2.x declarative models (data-models.md §4), split into one module per
domain (component-map.md note 2 — the models-growth allowance) once the single-file
`db/models.py` crossed the `check-file-length` hook's warn threshold in group C.

Every class is re-exported here so `from src.db.models import X` keeps working
regardless of which submodule actually defines `X` — no caller outside this package
needs to know about the split.
"""

from __future__ import annotations

from src.db.models.advisor import AdvisorOverride
from src.db.models.audit import AuditLogEntry
from src.db.models.goals import Goal, GoalProgressSnapshot
from src.db.models.holdings import AssetClass, Holding, NavSnapshot
from src.db.models.rebalancing import RebalancingRecommendation, RebalancingThreshold
from src.db.models.recommendation import AllocationTemplate
from src.db.models.risk_profile import RiskBandAssignment, RiskBandRule, RiskProfileAnswer
from src.db.models.user import Customer, User

__all__ = [
    "AdvisorOverride",
    "AllocationTemplate",
    "AssetClass",
    "AuditLogEntry",
    "Customer",
    "Goal",
    "GoalProgressSnapshot",
    "Holding",
    "NavSnapshot",
    "RebalancingRecommendation",
    "RebalancingThreshold",
    "RiskBandAssignment",
    "RiskBandRule",
    "RiskProfileAnswer",
    "User",
]
