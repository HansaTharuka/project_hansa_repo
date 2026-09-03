# Component Map — WealthWise

Routes every one of the 41 stories in `specs/stories/` to the specific files it creates or modifies. Paths are relative to the repository root and follow `folder-structure.md` exactly.

**Reading the table:** *Creates* means the story authors the file; *Modifies* means the story adds to a file an earlier story created. A file appearing in several rows is expected — routers, `db/models.py`, `types/requests.py` and `types/responses.py` accumulate across stories.

Execution order is `specs/stories/dependency-graph.md` groups A → H.

---

## Epic E1 — Platform Foundation

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E1-S1** Core domain types and schemas | Types / A | **Creates:** `backend/src/types/enums.py`, `backend/src/types/entities.py`, `backend/src/types/fixedpoint.py`, `backend/src/types/errors.py`, `frontend/src/types/entities.ts` | `backend/tests/unit/test_types_entities.py`, `backend/tests/unit/test_fixedpoint.py`, `backend/tests/architecture/test_no_float_in_domain.py`, `frontend/src/types/entities.test.ts` |
| **E1-S2** Application configuration | Config / A | **Creates:** `backend/src/core/config.py`, `backend/.env.example`, `frontend/.env.example`, `.gitignore` | `backend/tests/unit/test_config.py` |
| **E1-S3** DB engine, migrations, seed repository | Repository / B | **Creates:** `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial_users_customers.py` … `0008_advisor_override.py` (full chain, see note 1), `backend/src/db/base.py`, `backend/src/db/engine.py`, `backend/src/db/session.py`, `backend/src/db/models.py`, `backend/src/db/seed.py`, `backend/src/domain/auth/repository.py`, `backend/seed/demo_accounts.json`, `backend/pyproject.toml` | `backend/tests/conftest.py`, `backend/tests/factories.py`, `backend/tests/repository/test_migrations.py`, `backend/tests/repository/test_seed.py`, `backend/tests/repository/test_user_repository.py` (SQL-injection-as-literal assertion, AC4) |
| **E1-S4** Health endpoint + structured logging | API / C | **Creates:** `backend/src/app/main.py`, `backend/src/app/routers/health.py`, `backend/src/app/middleware/request_id.py`, `backend/src/app/middleware/request_log.py`, `backend/src/core/logging.py`, `backend/src/app/error_handlers.py` | `backend/tests/api/test_health.py`, `backend/tests/unit/test_logging_redaction.py` |

---

## Epic E2 — Authentication

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E2-S1** Auth service (bcrypt + JWT) | Service / C | **Creates:** `backend/src/core/security.py`, `backend/src/domain/auth/service.py`. **Modifies:** `backend/src/domain/auth/repository.py` | `backend/tests/unit/test_auth_service.py`, `backend/tests/unit/test_security.py` |
| **E2-S2** Login API endpoint | API / D | **Creates:** `backend/src/app/routers/auth.py`, `backend/src/app/dependencies.py` (`get_session`, `get_current_actor`, `require_role`). **Modifies:** `backend/src/types/requests.py`, `backend/src/types/responses.py`, `backend/src/app/main.py`, `backend/src/app/error_handlers.py` | `backend/tests/api/test_auth_login.py`, `backend/tests/api/test_auth_me.py`, `backend/tests/api/test_role_matrix.py` |
| **E2-S3** Login UI + role-based redirect | UI / E | **Creates:** `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/ProtectedRoute.tsx`, `frontend/src/auth/roleRedirect.ts`, `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/components/NavBar.tsx`, `frontend/src/components/LabeledField.tsx`, `frontend/src/components/ErrorMessage.tsx`, `frontend/src/styles/global.css`, `frontend/index.html`, `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/eslint.config.js`, `frontend/src/test/setup.ts` | `frontend/src/pages/Login.test.tsx`, `frontend/src/auth/AuthContext.test.tsx`, `frontend/src/auth/roleRedirect.test.ts`, `frontend/src/api/client.test.ts` |

---

## Epic E3 — Audit Trail

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E3-S1** Append-only audit repository | Repository / C | **Creates:** `backend/src/domain/audit/repository.py`. **Modifies:** `backend/src/db/models.py` (`AuditLogEntry` + its three indexes) | `backend/tests/repository/test_audit_repository.py`, `backend/tests/architecture/test_append_only.py` |
| **E3-S2** Central audit-writer service | Service / D | **Creates:** `backend/src/domain/audit/service.py` | `backend/tests/unit/test_audit_service.py` |
| **E3-S3** Audit log API | API / E | **Creates:** `backend/src/app/routers/audit.py`. **Modifies:** `backend/src/types/requests.py` (`AuditQuery`), `backend/src/types/responses.py` (`AuditPage`), `backend/src/app/main.py` | `backend/tests/api/test_audit_api.py` (includes the 405-on-write and 403-per-role assertions) |
| **E3-S4** Compliance audit-log UI | UI / F | **Creates:** `frontend/src/pages/compliance/AuditLog.tsx`, `frontend/src/api/audit.ts`, `frontend/src/components/DataTable.tsx`. **Modifies:** `frontend/src/router.tsx`, `frontend/src/lib/format.ts` | `frontend/src/pages/compliance/AuditLog.test.tsx`, `frontend/src/components/DataTable.test.tsx` |

---

## Epic E4 — Risk Profiling

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E4-S1** Questionnaire + versioned scoring-rule repository | Repository / C | **Creates:** `backend/src/domain/risk_profile/repository.py`. **Modifies:** `backend/src/db/models.py` (`RiskBandRule`, `RiskProfileAnswer`, `RiskBandAssignment`), `backend/src/db/seed.py` (rule version 1, ≥6 questions), `backend/seed/demo_accounts.json` | `backend/tests/repository/test_risk_profile_repository.py` |
| **E4-S2** Deterministic risk-band scoring service | Service / E | **Creates:** `backend/src/domain/risk_profile/scoring.py` (pure integer function), `backend/src/domain/risk_profile/service.py` | `backend/tests/unit/test_risk_scoring.py`, `backend/tests/unit/test_risk_profile_service.py` |
| **E4-S3** Risk-profile submission API | API / F | **Creates:** `backend/src/app/routers/risk_profile.py`. **Modifies:** `backend/src/types/requests.py`, `backend/src/types/responses.py`, `backend/src/app/main.py` | `backend/tests/api/test_risk_profile_api.py` |
| **E4-S4** Questionnaire UI + result screen | UI / G | **Creates:** `frontend/src/pages/customer/Questionnaire.tsx`, `frontend/src/pages/customer/RiskResult.tsx`, `frontend/src/pages/customer/Dashboard.tsx`, `frontend/src/api/riskProfile.ts`. **Modifies:** `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx` | `frontend/src/pages/customer/Questionnaire.test.tsx`, `frontend/src/pages/customer/RiskResult.test.tsx` |

---

## Epic E5 — Allocation Recommendation

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E5-S1** Versioned allocation-template repository | Repository / C | **Creates:** `backend/src/domain/recommendation/repository.py`. **Modifies:** `backend/src/db/models.py` (`AllocationTemplate` + `UNIQUE(risk_band, version)`), `backend/src/db/seed.py` (2 versions × 3 bands) | `backend/tests/repository/test_allocation_template_repository.py`, `backend/tests/architecture/test_allocation_sum.py` |
| **E5-S2** Allocation recommendation service | Service / F | **Creates:** `backend/src/domain/recommendation/horizon.py`, `backend/src/domain/recommendation/service.py` | `backend/tests/unit/test_horizon.py`, `backend/tests/unit/test_recommendation_service.py` |
| **E5-S3** Recommendation API endpoint | API / G | **Creates:** `backend/src/app/routers/recommendation.py`. **Modifies:** `backend/src/types/responses.py`, `backend/src/app/main.py` | `backend/tests/api/test_recommendation_api.py` |
| **E5-S4** Recommended allocation UI view | UI / H | **Creates:** `frontend/src/pages/customer/Allocation.tsx`, `frontend/src/api/recommendation.ts`, `frontend/src/lib/money.ts`. **Modifies:** `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx` | `frontend/src/pages/customer/Allocation.test.tsx`, `frontend/src/lib/money.test.ts` |

---

## Epic E6 — Asset Price Feed, Holdings & Drift

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E6-S1** AssetClass/NavSnapshot repository + CSV loader | Repository / C | **Creates:** `backend/src/domain/holdings/repository.py`, `backend/src/domain/holdings/csv_loader.py`, `backend/seed/asset_classes.csv`, `backend/seed/nav_initial.csv`. **Modifies:** `backend/src/db/models.py` (`AssetClass`, `NavSnapshot`, `Holding` + `UNIQUE(asset_class_id, price_date)`), `backend/src/db/seed.py` | `backend/tests/repository/test_holdings_repository.py`, `backend/tests/repository/test_csv_loader.py` |
| **E6-S2** NAV 'advance a day' refresh service | Service / D | **Creates:** `backend/src/domain/holdings/service.py` (`advance_day` orchestration). **Modifies:** `backend/src/core/clock.py` | `backend/tests/unit/test_advance_day.py` |
| **E6-S3** Holdings + drift calculation service | Service / D | **Creates:** `backend/src/domain/holdings/drift.py` (pure fixed-point). **Modifies:** `backend/src/domain/holdings/service.py`, `backend/src/domain/rebalancing/threshold_repository.py` (active-threshold read) | `backend/tests/unit/test_drift.py`, `backend/tests/architecture/test_no_float_in_domain.py` |
| **E6-S4** Holdings/drift + advance-day admin API | API / E | **Creates:** `backend/src/app/routers/holdings.py`, `backend/src/app/routers/admin.py` (advance-day only at this story). **Modifies:** `backend/src/types/responses.py`, `backend/src/app/main.py`, `backend/src/app/error_handlers.py` (`DAY_ALREADY_ADVANCED` → 409) | `backend/tests/api/test_holdings_api.py`, `backend/tests/api/test_advance_day_api.py` |
| **E6-S5** Holdings and drift UI view | UI / F | **Creates:** `frontend/src/pages/customer/Holdings.tsx`, `frontend/src/api/holdings.ts`, `frontend/src/components/EmptyState.tsx`. **Modifies:** `frontend/src/lib/money.ts`, `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx` | `frontend/src/pages/customer/Holdings.test.tsx` |

---

## Epic E7 — Goals & Progress Tracking

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E7-S1** Goal + GoalProgressSnapshot repository | Repository / C | **Creates:** `backend/src/domain/goals/repository.py`. **Modifies:** `backend/src/db/models.py` (`Goal`, `GoalProgressSnapshot` + `UNIQUE(goal_id, price_date)`), `backend/src/db/seed.py` | `backend/tests/repository/test_goals_repository.py` |
| **E7-S2** Goal management service | Service / D | **Creates:** `backend/src/domain/goals/service.py` | `backend/tests/unit/test_goal_service.py` |
| **E7-S3** Goal progress recompute on NAV refresh | Service / E | **Creates:** `backend/src/domain/goals/progress.py` (pure, with the 200.00% cap). **Modifies:** `backend/src/domain/goals/service.py`, `backend/src/domain/holdings/service.py` (invoke recompute inside `advance_day`) | `backend/tests/unit/test_goal_progress.py` |
| **E7-S4** Goals API (CRUD + progress) | API / F | **Creates:** `backend/src/app/routers/goals.py`. **Modifies:** `backend/src/types/requests.py`, `backend/src/types/responses.py`, `backend/src/app/main.py` | `backend/tests/api/test_goals_api.py` |
| **E7-S5** Goals UI (list, create/edit, progress) | UI / G | **Creates:** `frontend/src/pages/customer/Goals.tsx`, `frontend/src/api/goals.ts`. **Modifies:** `frontend/src/components/LabeledField.tsx`, `frontend/src/components/ErrorMessage.tsx`, `frontend/src/lib/money.ts`, `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx` | `frontend/src/pages/customer/Goals.test.tsx` |

---

## Epic E8 — Rebalancing

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E8-S1** RebalancingRecommendation repository | Repository / C | **Creates:** `backend/src/domain/rebalancing/repository.py`, `backend/src/domain/rebalancing/threshold_repository.py`. **Modifies:** `backend/src/db/models.py` (`RebalancingRecommendation`, `RebalancingThreshold`), `backend/src/db/seed.py` (threshold version 1, `threshold_bps = 500`) | `backend/tests/repository/test_rebalancing_repository.py`, `backend/tests/repository/test_threshold_repository.py` |
| **E8-S2** Rebalancing engine service | Service / E | **Creates:** `backend/src/domain/rebalancing/engine.py` (pure BUY/SELL proposal), `backend/src/domain/rebalancing/service.py`. **Modifies:** `backend/src/domain/holdings/service.py` (invoke evaluation inside `advance_day`) | `backend/tests/unit/test_rebalancing_engine.py`, `backend/tests/unit/test_rebalancing_service.py` (includes the `kyc_verified = false` gate and zero-holdings no-op) |
| **E8-S3** Rebalancing API (list, accept, dismiss) | API / F | **Creates:** `backend/src/app/routers/rebalancing.py`. **Modifies:** `backend/src/types/requests.py`, `backend/src/types/responses.py`, `backend/src/app/main.py`, `backend/src/app/error_handlers.py` (`ALREADY_RESOLVED` → 409) | `backend/tests/api/test_rebalancing_api.py` |
| **E8-S4** Rebalancing recommendations UI | UI / G | **Creates:** `frontend/src/pages/customer/Rebalancing.tsx`, `frontend/src/api/rebalancing.ts`. **Modifies:** `frontend/src/components/EmptyState.tsx`, `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx` | `frontend/src/pages/customer/Rebalancing.test.tsx` |

---

## Epic E9 — Advisor Workflows

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E9-S1** AdvisorOverride repository | Repository / C | **Creates:** `backend/src/domain/advisor/repository.py`. **Modifies:** `backend/src/db/models.py` (`AdvisorOverride`) | `backend/tests/repository/test_advisor_override_repository.py`, `backend/tests/architecture/test_append_only.py` |
| **E9-S2** Override + manual-recommendation service | Service / F | **Creates:** `backend/src/domain/advisor/service.py` | `backend/tests/unit/test_advisor_service.py` |
| **E9-S3** Advisor API | API / G | **Creates:** `backend/src/app/routers/advisor.py`. **Modifies:** `backend/src/types/requests.py`, `backend/src/types/responses.py`, `backend/src/app/main.py` | `backend/tests/api/test_advisor_api.py` |
| **E9-S4** Advisor UI (list, drill-in, override, modal) | UI / H | **Creates:** `frontend/src/pages/advisor/CustomerList.tsx`, `frontend/src/pages/advisor/CustomerDetail.tsx`, `frontend/src/pages/advisor/OverrideForm.tsx`, `frontend/src/pages/advisor/ManualRecommendationModal.tsx`, `frontend/src/api/advisor.ts`, `frontend/src/components/Modal.tsx`. **Modifies:** `frontend/src/router.tsx` (drill-in route only — the modal is **not** a route) | `frontend/src/pages/advisor/CustomerList.test.tsx`, `frontend/src/pages/advisor/CustomerDetail.test.tsx`, `frontend/src/pages/advisor/OverrideForm.test.tsx`, `frontend/src/pages/advisor/ManualRecommendationModal.test.tsx` |

---

## Epic E10 — Admin Console

| Story | Layer / Group | Implementation files | Test files |
|---|---|---|---|
| **E10-S1** Versioned rule/template publish repository | Repository / D | **Creates:** `backend/src/domain/admin/repository.py`. **Modifies:** `backend/src/domain/risk_profile/repository.py` (publish path), `backend/src/domain/recommendation/repository.py` (publish path), `backend/src/domain/rebalancing/threshold_repository.py` (publish path), `backend/src/db/models.py` (`UNIQUE(version)` on rules and thresholds, `UNIQUE(risk_band, version)` on templates, `UNIQUE(code)` on asset classes) | `backend/tests/repository/test_admin_publish_repository.py`, `backend/tests/architecture/test_append_only.py` |
| **E10-S2** Admin publish service | Service / E | **Creates:** `backend/src/domain/admin/service.py` | `backend/tests/unit/test_admin_publish_service.py` (sum-to-100 rejection, <6-question rejection, concurrent-publish conflict) |
| **E10-S3** Admin API | API / F | **Modifies:** `backend/src/app/routers/admin.py` (adds rule/template/threshold publish + asset-class CRUD to the advance-day router created in E6-S4), `backend/src/types/requests.py`, `backend/src/types/responses.py`, `backend/src/app/error_handlers.py` (`VERSION_CONFLICT`, `TEMPLATE_SUM_INVALID`, `DUPLICATE_ASSET_CLASS_CODE`) | `backend/tests/api/test_admin_api.py` |
| **E10-S4** Admin UI | UI / G | **Creates:** `frontend/src/pages/admin/AdminHome.tsx`, `frontend/src/pages/admin/RuleEditor.tsx`, `frontend/src/pages/admin/TemplateEditor.tsx`, `frontend/src/pages/admin/AssetClasses.tsx`, `frontend/src/pages/admin/ThresholdEditor.tsx`, `frontend/src/api/admin.ts`. **Modifies:** `frontend/src/lib/money.ts` (basis-point running total), `frontend/src/router.tsx`, `frontend/src/components/NavBar.tsx` | `frontend/src/pages/admin/RuleEditor.test.tsx`, `frontend/src/pages/admin/TemplateEditor.test.tsx`, `frontend/src/pages/admin/AssetClasses.test.tsx`, `frontend/src/pages/admin/ThresholdEditor.test.tsx` |

---

## Notes

1. **Migrations are all authored in E1-S3.** E1-S3 AC1 requires that running the migration command against a fresh database creates tables for **all 14 entities**, so the full revision chain `0001` … `0008` (plus `RebalancingThreshold` in `0007`) is written there. `data-models.md` §6 attributes each revision to the story whose entity it serves — that is provenance, not authorship. Later stories add repository code against tables that already exist; none of them edits a committed migration (NFR-05).

2. **`backend/src/db/models.py` is modified by every repository story.** It is the single SQLAlchemy table-definition module. If it approaches the `check-file-length` hook's limit it should be split into `models/` with one module per domain, keeping the same import surface — not thinned by removing constraints.

3. **`backend/src/app/routers/admin.py` is created by E6-S4, not E10-S3.** The advance-a-day endpoint is admin-role but belongs to the holdings epic, and it lands first in the dependency graph (group E vs group F). E10-S3 extends the same router.

4. **`frontend/src/lib/money.ts` is created by E5-S4** — the first UI story that renders a percentage — and extended by E6-S5, E7-S5 and E10-S4. All fixed-point display and arithmetic goes through it; no other frontend file may call `parseFloat` on a money or percent value (NFR-01).

5. **Architecture tests are written once and extended.** `test_append_only.py`, `test_no_float_in_domain.py` and `test_allocation_sum.py` each appear against several stories because each new append-only repository or new fixed-point module adds a case to the existing test module (NFR-08).

6. **The manual-recommendation modal creates no backend table.** E9-S3 and E9-S4 route it through `backend/src/domain/audit/service.py` as an `AuditLogEntry` with `entity_type = "ManualRecommendation"` (`system-design.md` §6.4).

---

## Coverage Check

41 stories, 41 rows: E1 ×4, E2 ×3, E3 ×4, E4 ×4, E5 ×4, E6 ×5, E7 ×5, E8 ×4, E9 ×4, E10 ×4 = 41.

(`specs/stories/` contains 42 files: these 41 stories plus `dependency-graph.md`.)

Every story has at least one implementation file and at least one test file, satisfying the rubric requirement that every spec acceptance criterion is traceable to at least one test.
