"""Pydantic request models for the advisor router (E9-S3; api-contracts.md
§11.3-§11.4).

Types layer (`.claude/architecture.md`): this module imports nothing beyond
`pydantic` itself.
"""

from __future__ import annotations

from pydantic import BaseModel


class AdvisorOverrideRequest(BaseModel):
    """api-contracts.md §11.3. `reason`/`note` are optional at this layer so
    a missing `reason` reaches `domain.advisor.service.override_risk_band`'s
    own check and surfaces as 422 `REASON_REQUIRED` through the standard
    error envelope, rather than FastAPI's generic validation-error shape.
    `previous_band` and `advisor_id` are server-derived and have no field
    here at all.
    """

    new_band: str
    reason: str | None = None
    note: str | None = None


class ManualRecommendationRequest(BaseModel):
    """api-contracts.md §11.4. `note` is optional at this layer for the same
    reason as `AdvisorOverrideRequest.reason` — the missing/blank/over-length
    check happens in `domain.advisor.service.log_manual_recommendation`.
    """

    note: str | None = None
