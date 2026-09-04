# Iteration Log — WealthWise

Evaluator iteration history per group, appended after each ratchet-gate verdict.

---

## Group A — 2026-09-03

- **Verdict:** PASS
- **Stories:** E1-S1 (core domain types/schemas), E1-S2 (application configuration)
- **Sprint contract:** sprint-contracts/A.json
- **Summary:** Types layer (14 BRD entities + RebalancingThreshold, fixed-point money/percent, closed enums) and config layer (typed Settings, fail-loud on missing required env var) delivered. Evaluator tightened the draft: added backend/pyproject.toml to files_must_exist, added 5 unit checks, fixed 3 internally-inconsistent checks, replaced a layering check that referenced a test module no story owns, and recorded the import-path deviation (`src.*` packages, not top-level `types`/`core`, to avoid shadowing the stdlib `types` module) as note 3a for the lead to route.
- **Gate results:** tests pass, ruff/mypy clean, coverage 100% (>= 80% floor, no baseline to ratchet against yet), architecture checks pass. api/playwright/design checks empty by design (no app yet).
- **Commit:** b9e1a4f "feat: implement group A (E1-S1 core types, E1-S2 config)"
- **Features:** F001-F010 passing (10/207)

## Group B — 2026-09-04

- **Verdict:** PASS
- **Stories:** E1-S3 (database engine, migrations, seed-data repository)
- **Sprint contract:** sprint-contracts/B.json
- **Summary:** Full Alembic migration chain (0001-0008, all 15 tables), SQLAlchemy 2.x repository infrastructure (base/engine/session/models), idempotent seed loader, and a parameterized-query-only auth repository. Sprint contract negotiation surfaced and resolved a genuine spec ambiguity (note 2): whether E1-S3's own seed.py must insert real `RiskBandAssignment` rows to satisfy its own AC2 ("seed script inserts customers spanning all three risk bands"), versus deferring to a later story via a JSON intent-tag. The evaluator confirmed real rows are required — no later story's acceptance criteria (checked E4-S1.md directly) ever creates one, and data-models.md section 4.4's soft reference (no FK) exists precisely so the referencing row can be written before RiskBandRule version 1 exists. A duplicate-orchestrator race occurred during this group's contract negotiation (two generator drafts and a stale teammate loose in the session); both the orchestrator and the evaluator independently reached the same resolution before the evaluator finalized the contract, so no rework was needed once ownership was consolidated to a single orchestrator.
- **Gate results:** 278 tests pass, 100% coverage (matches 100% baseline, well above 80% floor), ruff clean, mypy clean on src/db + src/domain (and no regression on src/types + src/core), layering/no-float/parameterized-query/secrets scans clean, alembic chain verified linear with one head. Evaluator independently re-ran every check (not generator self-report) and returned PASS. api/playwright/design checks empty by design (repository-layer-only group, no app yet).
- **Commit:** 19a53a6 "feat: implement group B (E1-S3 DB engine, migrations, seed repository)"
- **Features:** F011-F015 passing (15/207 cumulative)
## Group D — 2026-09-04

- **Verdict:** PASS (after one fix cycle)
- **Stories:** E2-S2 (login API endpoint), E3-S2 (central audit-writer service), E6-S2 (NAV advance-a-day refresh service), E6-S3 (holdings drift calculation service), E7-S2 (goal management service), E10-S1 (versioned rule/template publish repository)
- **Sprint contract:** sprint-contracts/D.json
- **Summary:** POST /api/auth/login and GET /api/auth/me (the first protected endpoint), the central audit-writer every domain service must funnel through, the advance-a-day NAV/holdings-revaluation/drift-recompute orchestration, pure fixed-point drift calculation, goal create/edit with ownership enforcement, and admin asset-class CRUD plus DB-level monotonic-version uniqueness tests for the three existing versioned-publish repositories. Two judgment calls were independently verified sound: E6-S2 AC2's double-advance rejection relies on the `UNIQUE(asset_class_id, price_date)` DB constraint rather than a check-then-act read (cross-checked against system-design.md §9.5 and D11), with the race simulated via a monkeypatched `IntegrityError` since two sequential in-process calls can never naturally collide; the simulation genuinely exercises `advance_day`'s own try/except/rollback/translate logic, not just the mock. E10-S1's scoping (only `update_asset_class` and DB-uniqueness tests are new; AC1/AC3/AC5 were already satisfied by Group B/C's `publish_rule`/`publish_template`/`publish_threshold`) was independently re-verified against all three modules directly and confirmed correct, not under-scoped.
- **Fix cycle:** Evaluator's first pass at sign-off found one genuine layering violation (not self-reported) — `backend/src/app/routers/auth.py` imported `src.domain.auth.repository.get_user_by_id` directly for the GET /api/auth/me handler, bypassing the service layer, the exact "thin pass-through router" pattern design decision D3 rejects. Fix: added `domain.auth.service.get_user_details` as the proper service-layer wrapper and pointed the router at it instead — no test assertions changed. Re-ran the full gate after the fix: clean.
- **Gate results:** 463 tests pass, 100% coverage (1402/1402 statements, matches 100% baseline), ruff clean, mypy clean (52 source files, 0 errors), architecture suite (no_float/append_only/allocation_sum) 52/52 passing, all four layering scans clean (zero matches), detect-secrets clean.
- **Commit:** 239cd1e "feat: implement group D (E2-S2, E3-S2, E6-S2, E6-S3, E7-S2, E10-S1)"
- **Features:** F026-F030, F041-F045, F102-F106, F107-F111, F127-F131, F188-F192 passing (90/207 cumulative)
