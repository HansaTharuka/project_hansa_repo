# Evaluator Report — WealthWise

## Group A

**Date:** 2026-09-04
**Stories:** E1-S1 (core domain types and schemas), E1-S2 (application configuration)
**Features:** F001–F010
**Contract:** `sprint-contracts/A.json` (finalized at this sign-off; immutable)
**Verdict: PASS**

### Contract finalization

- Audited AC coverage in both directions. All 10 acceptance criteria across E1-S1 and E1-S2 have at least one check; every check traces to an AC or to a normative design-doc requirement. No check removed; none was untraceable.
- Tightened `architecture_checks.layering` — the draft regex matched only bare `app|db|domain` / `core` and would have been blind to the `src.`-prefixed import form the delivered code actually uses. Both invocations now accept an optional `src.` prefix.
- Corrected `ut-026`: the draft's blanket "every `*_id` is int" rule contradicted `data-models.md` §4.3/§4.12/§4.14, where `question_id`, `recommendation_id` and `entity_id` are TEXT.
- Added non-vacuity requirements to `no_float` and `ut-020` (the detector must be proven to flag a known-offending module).
- Added note 3a recording the import-path deviation and its two downstream spec gaps (see Flagged below).

### Checks executed

Architecture checks (all from repo root / `backend/`):

- `files_must_exist` — all 15 paths present.
- `layering` — both ripgrep scans return no matches (exit 1). `src/types` imports only stdlib, pydantic and `src.types.enums`; `src/core` only stdlib and pydantic/pydantic-settings.
- `typing` — `uv run mypy src/types src/core` → 0 errors, 7 files. mypy `strict = true`, no `ignore_errors`, no `type: ignore` anywhere in `src/`.
- `no_float` — `uv run pytest tests/architecture/test_no_float_in_domain.py` → 9 passed, covering `src/types` and `src/core`.
- `env_vars` — `uv run detect-secrets scan src .env.example` → empty `results` object.
- `folder_structure` — no file created outside the group's declared surface; nothing under `src/app/`, `src/db/`, `src/domain/`.
- `migrations` — not required for this group; none present, correctly.

Suite and quality gates:

- `uv run pytest -x -q` → **214 passed**.
- `uv run ruff check .` → all checks passed.
- `uv run pytest --cov=src --cov-report=term-missing -q` → **100%** (249 statements, 0 missed) across all 7 source modules.
- Per-file: `test_types_entities.py` 125, `test_config.py` 49, `test_fixedpoint.py` 31, `test_no_float_in_domain.py` 9.

Unit-test cross-checks (contract id → actual test content, verified by reading the test modules, not by trusting their names): ut-001, ut-002, ut-003, ut-004, ut-005, ut-006, ut-007, ut-008, ut-009, ut-010, ut-012, ut-013, ut-016, ut-017, ut-019, ut-020, ut-022, ut-024, ut-025, ut-026, ut-027, ut-028, ut-029, ut-030 — all genuinely covered. The test module's `EXPECTED_FIELDS` table was cross-checked field-by-field against `data-models.md` §4.1–§4.15 and matches exactly, so the shape assertions are anchored to the spec rather than to the implementation.

Independent verification (run outside the project's own pytest suite, to avoid trusting the tests):

- E1-S2 AC2 — `Settings()` with no environment raises `MissingEnvironmentVariableError` naming both `DATABASE_URL` and `JWT_SECRET`.
- E1-S2 AC1 — defaults resolve to `5` and `60`, both `int`.
- E1-S1 AC1 — all 14 BRD §9 entities importable as Pydantic models.
- E1-S1 AC2 — all five money annotations resolve to `decimal.Decimal`.
- E1-S1 AC3 — enum member sets exact; `role='superuser'` raises `ValidationError`.
- `fixedpoint` round-trips: `2500000 → "25000.00"`, `-725 → "-7.25"`, `Decimal("12.34565") → "12.3457"` (ROUND_HALF_UP).
- E1-S1 AC5 — `frontend/src/types/entities.ts` read directly: all 14 entities plus `RebalancingThreshold`, snake_case names identical to the Pydantic models, money/percent/units typed `string`, `threshold_bps` and `percent_bps` the documented `number` exceptions, closed literal unions for `Role` / `RiskBand` / `RecommendationStatus`. Verified statically — the frontend toolchain arrives in E2-S3.

Not run, by contract design (`runtime_expectations.app_expected_running: false`): health probe, api_checks, playwright_checks, design_checks. Group A ships no router, no endpoint and no page.

### Flagged for the lead (does not block Group A)

1. **Import-path deviation.** `folder-structure.md` §2 calls for hatchling `packages = ["src/app", "src/core", "src/types", ...]` so modules resolve as top-level `types.*` / `core.*` / `app.main`. The generator instead used `[tool.uv] package = false` with `pythonpath = ["."]` and `src.*` imports — correctly, since a top-level package named `types` shadows the stdlib `types` module that `enum`, `re` and `dataclasses` import at interpreter start-up. Consequences: `folder-structure.md` §2's import-path note needs an amendment, and `project-manifest.json`'s start command `uv run uvicorn app.main:app` will not resolve — E1-S4 (group C) needs `src.app.main:app` or equivalent.
2. **`tests/architecture/test_layering.py` has no owner.** It appears in `folder-structure.md` §2 but is attributed to no story in `component-map.md`. Group A's layering gate is a static import scan instead; the pytest module needs routing to a later story.
3. **Contract-shape documentation inconsistency.** `.claude/templates/sprint-contract.json` nests the check arrays under a `contract` object and omits `unit_test_checks`, while `.claude/skills/evaluate/SKILL.md` reads them at top level. The top-level shape is operative; the template should be reconciled.

## Group B

**Date:** 2026-09-04
**Stories:** E1-S3 (database engine, migrations, seed-data repository)
**Features:** F011–F015
**Contract:** `sprint-contracts/B.json` (finalized at this sign-off; immutable)
**Verdict: PASS**

### Contract finalization

- Audited AC coverage in both directions: all 5 acceptance criteria have at least one check (AC1: ut-031–034 + `migrations`; AC2: ut-035, ut-036; AC3: ut-037, ut-038; AC4: ut-039, ut-040 + `parameterized_queries`; AC5: ut-041, ut-042). No check removed.
- Resolved a genuine spec ambiguity (contract note 2): whether E1-S3's own seed.py must insert real `RiskBandAssignment` rows to satisfy AC2 ("customers spanning all three risk bands"), or defer to a later story via a JSON intent-tag. Confirmed real rows are required — no later story's ACs ever create one (checked E4-S1.md directly), and data-models.md §4.4's soft reference (no FK) exists precisely so the referencing row can be written before `RiskBandRule` version 1 exists. Tightened ut-036 accordingly to require exactly one row per customer.
- Added ut-044 (previously missing): proves `alembic/env.py` resolves its target DB from `core.config.Settings.database_url`, never a hardcoded path.
- Tightened `migrations` architecture check to an executable `alembic heads` + `alembic history --verbose` command rather than a bare test-file reference.
- Added `architecture_checks.parameterized_queries` and `env_vars` (re-scanning the new `seed/` directory, out of scope for Group A's scan).
- A duplicate-orchestrator race occurred during this group's negotiation (two generator drafts, a stale teammate loose in the session); both the orchestrator and the evaluator independently reached the same resolution on note 2 before the evaluator finalized the contract, so no rework was needed once ownership was consolidated.

### Checks executed

- `uv run pytest -x -q` → **278 passed**.
- `uv run pytest --cov=src --cov-report=term-missing -q` → **100%** coverage (matches 100% baseline).
- `uv run ruff check .` → all checks passed.
- `uv run mypy src/db src/domain` → 0 errors.
- `alembic heads` → one head, no branch point; `alembic history --verbose` → linear chain 0001–0008.
- Layering (2 ripgrep scans, both carried forward from Group A's dual bare/`src.`-prefixed pattern) → no matches.
- `no_float` (`pytest tests/architecture/test_no_float_in_domain.py`) → passes, non-vacuity self-check intact.
- `parameterized_queries` scan over `domain/auth/repository.py` → no matches.
- `detect-secrets scan src seed` → empty results.
- `folder_structure` → every `files_must_exist` path present at its documented location; no file created outside the group's declared surface.
- Unit-test cross-checks ut-031 through ut-044 verified by reading the test modules, not by trusting their names.

Not run, by contract design (`app_expected_running: false`): health probe, api/playwright/design checks. No FastAPI app exists until Group C.

### Flagged for the lead (does not block Group B)

1. `test_layering.py` remains unowned (carried forward from Group A note 4) — still a static ripgrep scan standing in for it.
2. Import-path convention (`src.*`, not top-level `db.*`/`domain.*`) carried forward unchanged from Group A note 3a; no new deviation introduced here.

## Group C

**Date:** 2026-09-04
**Stories:** E1-S4 (health + structured logging), E2-S1 (auth service), E3-S1 (audit repo), E4-S1 (risk-profile repo), E5-S1 (allocation-template repo), E6-S1 (asset-class/NAV repo), E7-S1 (goal repo), E8-S1 (rebalancing-recommendation + threshold repo), E9-S1 (advisor-override repo)
**Features:** F016–F025, F036–F040, F056–F060, F077–F081, F097–F101, F122–F126, F147–F151, F168–F172
**Contract:** `sprint-contracts/C.json` (finalized at this sign-off; immutable)
**Verdict: PASS**

### Contract finalization

- Audited AC coverage in both directions across all 9 stories' 45 acceptance criteria: every AC has at least one check; every check traces to an AC, NFR, or normative design-doc requirement.
- **Layering resolution (the most consequential judgment call in this group's contract):** `folder-structure.md` §4's table, read in isolation, could be misread as forbidding GET `/health`'s own DB connectivity probe from touching `db/` at all. `system-design.md` §2.1's table is more precise and was followed instead: its API row's "May NOT import from" is scoped to `domain/*/repository.py` specifically, not `backend/src/db/` as a whole — corroborated by already-delivered Group B code (`db/session.py`'s own docstring commits `app/dependencies.py` to importing it directly in E2-S2). Resolution: `app/` may import `db/session.py`/`db/engine.py` directly for connection plumbing, but never `db/models.py` and never any `domain/*/repository.py` module. A third static scan was added to close the `db/models.py` gap the generator's draft left open. Flagged to the lead: `folder-structure.md` §4 should be amended to state this distinction explicitly.
- Found and fixed a real coverage gap (note 5): `RebalancingThreshold`/`threshold_repository.py` was required to exist by `files_must_exist` (per component-map.md's E8-S1 row) but had zero behavioral checks in the generator's draft — no E8-S1 AC text names it. Added ut-088/ut-089/ut-090 (no-update/delete, versioned-publish pattern, seed value `threshold_bps = 500`), attached to F147 in the absence of a dedicated feature id.
- Re-verified (not merely accepted) the `append_only`/`allocation_sum` test-file ownership claims against component-map.md's literal per-row test-file columns for all 5 other repository stories, and against data-models.md §4's per-entity mutability markers (RiskBandRule/AllocationTemplate: insert-only-versioned; Goal: genuinely mutable; AssetClass/Holding: mutable; NavSnapshot/GoalProgressSnapshot: genuinely append-only) — confirmed correct as drafted.
- Resolved the `migrations_unchanged` placeholder commit to the concrete `a9c761f`.
- Rejected two live fault-injection alternatives for the 503 `DATABASE_UNAVAILABLE` branch (breaking the shared running instance mid-evaluation; renaming the SQLite file out from under a live engine — unreliable specifically on Windows) as disproportionate; covered instead by a monkeypatched unit test (ut-046).

### Checks executed

- Health-check retry/backoff loop against `http://localhost:8000/health` succeeded before `api_checks`/`performance_checks` ran; `GET /health` → 200, `{"status":"ok","database":"connected"}`, under 1000ms.
- `X-Request-ID` echoed/generated on the response and cross-checked against structured log output for the same request.
- `uv run pytest -x -q` → **380/380 passed**.
- `uv run pytest --cov=src --cov-report=term-missing -q` → **100%** coverage.
- `uv run ruff check .` → all checks passed.
- `uv run mypy src/app src/core src/domain src/db` → 0 errors.
- Layering (4 static scans, including the new `db/models.py` scan) → no matches.
- `no_float`, `append_only`, `allocation_sum` architecture suites → all passing, including the non-vacuity self-checks.
- `parameterized_queries` scan over all 9 new/extended repository-adjacent modules → no matches.
- `detect-secrets scan src seed` → empty results.
- `git diff --stat a9c761f..HEAD` over the alembic tree → empty (migrations unchanged).
- Unit-test cross-checks ut-045 through ut-090 verified by reading the test modules.

`design_checks` empty by design — no UI exists until Group E's E2-S3.

### Flagged for the lead (does not block Group C)

1. `folder-structure.md` §4's directory-to-layer table is imprecise relative to `system-design.md` §2.1's on the `db/`-vs-`domain/*/repository.py` distinction (see layering resolution above) — should be amended so this does not need re-litigating in a later group.
2. Bare `rg` is not on PATH in this evaluator's shell environment; ripgrep-based checks were executed via the evaluator agent's own Grep tool rather than shelled out — carried forward unchanged from Groups A/B, not a Group-C-specific defect.

## Group D

**Date:** 2026-09-04
**Stories:** E2-S2 (login API endpoint), E3-S2 (central audit-writer service), E6-S2 (NAV advance-a-day refresh service), E6-S3 (holdings drift calculation service), E7-S2 (goal management service), E10-S1 (versioned rule/template publish repository)
**Features:** F026–F030, F041–F045, F102–F111, F127–F131, F188–F192
**Contract:** `sprint-contracts/D.json` (finalized at this sign-off; immutable)
**Verdict: PASS (after one fix cycle)**

### Contract finalization

- Audited AC coverage in both directions across all 6 stories' 30 acceptance criteria; every check traces to an AC, NFR, or design-doc requirement.
- **Judgment call — E6-S2 AC2's double-advance rejection.** `advance_day` relies on the DB-level `UNIQUE(asset_class_id, price_date)` constraint (catch `IntegrityError` → `ConflictError`) rather than a check-then-act read. Verified sound against `system-design.md` §9.5 and D11: two sequential in-process calls can never naturally collide, so the losing writer's `IntegrityError` is simulated via monkeypatch on the low-level `insert_nav_snapshot` call only — the orchestration logic under test (try/except/rollback/translate) is genuinely exercised, not mocked.
- **Judgment call — E10-S1 scope.** AC1/AC3/AC5 were already satisfied by Group B/C's `publish_rule`/`publish_template`/`publish_threshold` (independently re-read, all three already implement `version = max + 1` with prior-row deactivation, already covered by Group B/C's own suites). Only `update_asset_class` (AC4) and DB-uniqueness tests (AC2) were genuinely new. Confirmed correct scoping, not under-scoping.
- Test-file naming deviates from component-map.md's E2-S2 row (three named files) — the delivered code consolidates into two (`test_auth_login.py`, `test_dependencies.py`). Judged an acceptable reorganization: every behavior component-map.md attributes to the three named files is present and passing under the two consolidated files.
- `api_checks` expressed as TestClient-equivalent checks backed by `tests/api/test_auth_login.py`'s existing suite rather than a separate live-uvicorn probe — judged equivalent in every respect that matters (real ASGI app, real dependency graph, real error handlers).

### Fix cycle

First evaluation pass at sign-off found one genuine, blocking layering violation (not self-reported): `backend/src/app/routers/auth.py` imported `src.domain.auth.repository.get_user_by_id` directly for the `GET /api/auth/me` handler — the exact "thin pass-through router" pattern design decision D3 names as rejected. Not a resolvable carve-out the way Group C's `db/session.py` exception was (system-design.md's directory-to-layer table has no exception listed for auth/me specifically). Required fix: add a thin `domain/auth/service.py` wrapper (`get_user_details`) and point the router at it instead — no test assertions changed. Fix applied and the full gate re-run: clean.

### Checks executed

- `uv run pytest -x -q` → **463/463 passed**.
- `uv run pytest --cov=src --cov-report=term-missing -q` → **100%** coverage (1402/1402 statements, matches baseline).
- `uv run ruff check .` → all checks passed.
- `uv run mypy src/` → 0 errors, 52 source files.
- All four layering scans (app→domain repo, app→db.models, domain→app, `raise HTTPException` under domain/) → zero matches after the fix.
- `no_float`, `append_only` architecture suites → 52/52 passing.
- `parameterized_queries` scan over the 6 modules touching SQL construction → no matches.
- `detect-secrets scan src seed` → empty results.
- `git diff --stat c5af99f..HEAD` over the alembic tree → empty (no schema change this group).
- Unit-test cross-checks ut-091 through ut-120 verified by reading the test modules.

`performance_checks` empty by design — no new endpoint this group carries its own latency requirement distinct from `/health`'s (already covered by Group C's contract).

### Flagged for the lead (does not block Group D)

1. The layering violation described above under "Fix cycle" was found and fixed within this same sign-off cycle — flagged here only so the pattern (`router → repository`, bypassing service) is visible for later groups' routers to avoid.
