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
