# Folder Structure — WealthWise

Canonical directory layout for the repository. `component-map.md` routes every story to files inside this tree; the `check-architecture` hook enforces the import direction between these directories.

Repository root: `D:\SELife\hardcore-projects\Virtusa\Project_hansa_repo`

---

## 1. Repository Root

```
Project_hansa_repo/
├── .claude/                     # Harness configuration — agents, slash commands, settings
│   ├── agents/                  # Agent definitions (planner, generator, evaluator, + WealthWise-specific agents)
│   └── commands/                # Slash-command definitions (/brd, /spec, /design, /build, /test, /evaluate)
├── hooks/                       # Executable hooks — layering, lint, typecheck, secrets, domain invariants
├── specs/                       # Source of truth (Spec-Is-Truth rule)
│   ├── brd/                     # Approved Business Requirements Document
│   ├── stories/                 # 42 story files + dependency-graph.md
│   ├── design/                  # This design package (8 files) + mockups/ and amendments/
│   └── test_artefacts/          # Test corpus directory named by project-manifest.json
├── sprint-contracts/            # Per-group sprint contracts gating /build
├── docs/                        # business-case.md and other narrative documentation
├── backend/                     # FastAPI monolith (section 2)
├── frontend/                    # React SPA (section 3)
├── .gitlab-ci.yml               # GitLab CI pipeline — lint, typecheck, test, coverage gate, Claude Code Action
├── .gitignore                   # Excludes .env, *.db, node_modules/, .venv/, coverage artefacts
├── project-manifest.json        # Fixed stack and evaluation URLs — not modified by build agents
├── design.md                    # Harness reference architecture
├── features.json                # Feature registry with pass/fail status
├── claude-progress.txt          # Session progress and pipeline position
├── learned-rules.md             # Ratchet memory — rules accumulated from past failures
├── failures.md                  # Failure log for pattern analysis
├── iteration-log.md             # Evaluator iteration history per feature
└── eval-scores.json             # Design scores per component per iteration
```

---

## 2. Backend — `backend/`

```
backend/
├── pyproject.toml               # Project metadata, dependencies, ruff/mypy/pytest configuration
├── uv.lock                      # Locked dependency graph — committed
├── alembic.ini                  # Alembic configuration; script_location = alembic
├── .env.example                 # Every required environment variable with placeholder values (E1-S2 AC5)
├── .env                         # Real local values — GIT-IGNORED, protected by the protect-env hook
├── wealthwise.db                # SQLite database file — GIT-IGNORED
├── alembic/                     # Migration tooling (NFR-05)
│   ├── env.py                   # Alembic runtime wiring — reads database_url from core.config
│   ├── script.py.mako           # Revision template
│   └── versions/                # APPEND-ONLY revisions; a committed file is never edited or deleted
├── seed/                        # Synthetic seed data (Synthetic-Data rule)
│   ├── asset_classes.csv        # Asset-class master: code, name
│   ├── nav_initial.csv          # Initial NAV per asset class for the first price_date
│   └── demo_accounts.json       # Seeded users/customers/goals/holdings definition
├── src/
│   ├── app/                     # API LAYER — the only layer that knows about HTTP
│   │   ├── main.py              # FastAPI app factory, router registration, CORS, startup seed load
│   │   ├── dependencies.py      # get_session, get_current_actor, require_role(*roles) — the NFR-04 boundary
│   │   ├── error_handlers.py    # Single domain-exception → HTTP-status mapping (api-contracts.md §1.4)
│   │   ├── middleware/          # Cross-cutting request handling
│   │   │   ├── request_id.py    # X-Request-ID generation/propagation (NFR-06)
│   │   │   └── request_log.py   # Structured JSON access log with the redaction allowlist (NFR-03, NFR-06)
│   │   └── routers/             # One router module per domain; routers never import repositories
│   │       ├── health.py        # GET /health
│   │       ├── auth.py          # POST /api/auth/login, GET /api/auth/me
│   │       ├── risk_profile.py  # GET questionnaire, POST submit, GET latest
│   │       ├── recommendation.py# GET /api/recommendation
│   │       ├── holdings.py      # GET /api/holdings
│   │       ├── goals.py         # Goals CRUD and progress
│   │       ├── rebalancing.py   # List, accept, dismiss
│   │       ├── advisor.py       # Customer list, drill-in, override, manual-recommendation
│   │       ├── admin.py         # advance-day, rule/template/threshold publish, asset-class CRUD
│   │       └── audit.py         # GET /api/audit — read-only, no write method registered
│   ├── core/                    # CONFIG LAYER — environment, security primitives, logging setup
│   │   ├── config.py            # Typed Settings from env vars; fails loudly on a missing required var (E1-S2 AC2)
│   │   ├── security.py          # bcrypt hash/verify, JWT encode/decode — no DB access
│   │   ├── logging.py           # Structured JSON logger factory and the PII redaction allowlist (NFR-03)
│   │   └── clock.py             # UTC now() indirection so tests can freeze time deterministically
│   ├── types/                   # TYPES LAYER — imports nothing project-local except other types modules
│   │   ├── enums.py             # Role, RiskBand, RecommendationStatus, TradeAction, AuditEntityType, AuditAction
│   │   ├── entities.py          # Pydantic models for all 14 entities + RebalancingThreshold (E1-S1)
│   │   ├── requests.py          # Request body/query models per endpoint
│   │   ├── responses.py         # Response models per endpoint
│   │   ├── errors.py            # Domain exception hierarchy — ValidationError, NotFoundError, ConflictError, …
│   │   └── fixedpoint.py        # THE single money/percent conversion module: minor units ↔ Decimal ↔ string, bps helpers (NFR-01)
│   ├── db/                      # REPOSITORY LAYER (shared infrastructure)
│   │   ├── base.py              # SQLAlchemy declarative Base and shared column conventions
│   │   ├── engine.py            # Engine creation, WAL pragma, foreign_keys pragma, busy timeout
│   │   ├── session.py           # Session factory and per-request unit-of-work helper
│   │   ├── models.py            # SQLAlchemy table definitions for all 15 tables
│   │   └── seed.py              # Idempotent seed loader — users, customers, asset classes, NAV, templates, threshold
│   └── domain/                  # DOMAIN MODULES — one directory per bounded area (BRD §8)
│       ├── auth/                # Ninth module, added beyond BRD §8's eight — rationale in the note below
│       │   ├── repository.py    # User / Customer reads — parameterized queries only (E1-S3 AC4)
│       │   └── service.py       # bcrypt verification and JWT issuance (E2-S1)
│       ├── risk_profile/
│       │   ├── repository.py    # RiskBandRule / RiskProfileAnswer / RiskBandAssignment — insert-only writes
│       │   ├── scoring.py       # Pure integer scoring function: answers + rule → risk band (no I/O)
│       │   └── service.py       # Submit flow, latest-assignment read, audit-writer call
│       ├── recommendation/
│       │   ├── repository.py    # AllocationTemplate — insert-only, sum-to-100 enforced at the boundary
│       │   ├── horizon.py       # Pure target_date → SHORT/MEDIUM/LONG bucketing
│       │   └── service.py       # Band + horizon → active template selection, audit-writer call
│       ├── holdings/
│       │   ├── repository.py    # AssetClass / NavSnapshot / Holding persistence
│       │   ├── csv_loader.py    # Idempotent seed-CSV load of asset classes and initial NAV
│       │   ├── drift.py         # Pure fixed-point drift computation (bps in, bps out, no I/O)
│       │   └── service.py       # advance_day orchestration, revaluation, drift read model
│       ├── rebalancing/
│       │   ├── repository.py    # RebalancingRecommendation — insert plus one-shot status transition
│       │   ├── threshold_repository.py # RebalancingThreshold — insert-only versioned publish/read
│       │   ├── engine.py        # Pure BUY/SELL proposal computation from drift and NAV
│       │   └── service.py       # kyc_verified gate, threshold comparison, accept/dismiss, audit-writer call
│       ├── goals/
│       │   ├── repository.py    # Goal (mutable) and GoalProgressSnapshot (insert-only)
│       │   ├── progress.py      # Pure percent_complete computation with the 200.00% cap
│       │   └── service.py       # Goal CRUD with ownership checks; recompute triggered by advance_day
│       ├── advisor/
│       │   ├── repository.py    # AdvisorOverride — insert-only
│       │   └── service.py       # Customer list/drill-in aggregation, override, manual-recommendation log
│       ├── admin/
│       │   ├── repository.py    # Versioned publish operations across rules, templates, thresholds, asset classes
│       │   └── service.py       # Publish validation (sum-to-100, ≥6 questions), version-race handling, audit
│       └── audit/
│           ├── repository.py    # AuditLogEntry — insert and filtered read ONLY; no update, no delete
│           └── service.py       # write_audit_entry(...) — the single audit entry point for every domain
└── tests/
    ├── conftest.py              # Shared fixtures — in-memory DB, seeded app client, per-role token factories
    ├── factories.py             # Deterministic test-data builders
    ├── unit/                    # Service- and pure-function-level tests, one module per domain
    ├── repository/              # Repository-level tests, including the "no update/delete method exists" assertions
    ├── api/                     # Endpoint tests per router, plus test_role_matrix.py driving api-contracts.md §14
    └── architecture/            # NFR-08 invariants as tests
        ├── test_layering.py             # No forbidden imports across layer boundaries
        ├── test_no_float_in_domain.py   # No float annotation or literal under src/domain and src/db (NFR-01)
        ├── test_append_only.py          # Insert-only repositories expose no update_*/delete_* callables (NFR-02)
        └── test_allocation_sum.py       # Every published template sums to exactly 10000 bps (AC-02)
```

**`domain/auth/` note.** BRD §8 enumerates eight domain modules and authentication is not among them, but authentication needs a repository (read a `User` by email) and a service (verify bcrypt, issue a JWT). Neither fits elsewhere without breaking the layering contract: `core/` is the Config layer and may not import `db/`, and a service may not live in `app/`. `domain/auth/` is therefore added as a ninth module. `core/security.py` keeps the pure primitives (hash, verify, encode, decode) with no database access, so the split stays clean.

**Import path note.** `project-manifest.json` starts the backend with `uv run uvicorn app.main:app --reload` from `backend/`. `pyproject.toml` therefore declares `src` as the package source root (hatchling `packages = ["src/app", "src/core", "src/types", "src/db", "src/domain"]`), so `uv run` installs the project and `app.main`, `domain.*`, `core.*`, `types.*`, `db.*` all resolve as top-level packages. This is what lets the tree match BRD §8's literal `src/domain/` requirement *and* the manifest's literal `app.main:app` start command.

---

## 3. Frontend — `frontend/`

```
frontend/
├── package.json                 # Scripts: dev, build, lint, typecheck, test, test:coverage
├── package-lock.json            # Locked dependency graph — committed
├── vite.config.ts               # Vite dev server on :5173, vitest configuration, coverage thresholds
├── tsconfig.json                # Strict TypeScript; no implicit any, no unchecked indexed access
├── tsconfig.node.json           # Config-file typechecking
├── eslint.config.js             # Lint rules, including the ban on parseFloat for money/percent values
├── index.html                   # Vite entry HTML
├── .env.example                 # VITE_API_BASE_URL placeholder
├── .env                         # Real local values — GIT-IGNORED
├── public/                      # Static assets served as-is
└── src/
    ├── main.tsx                 # React root, AuthProvider and router mount
    ├── App.tsx                  # Application shell — layout, navigation, error boundary
    ├── router.tsx               # Route table with per-route role guards
    ├── api/                     # HTTP access — the ONLY place fetch is called
    │   ├── client.ts            # Bearer-token attachment, X-Request-ID, error-envelope normalisation
    │   ├── auth.ts              # login, me
    │   ├── riskProfile.ts       # questionnaire, submit, latest
    │   ├── recommendation.ts    # getRecommendation
    │   ├── holdings.ts          # getHoldings
    │   ├── goals.ts             # list, create, update, progress
    │   ├── rebalancing.ts       # list, accept, dismiss
    │   ├── advisor.ts           # customers, detail, override, manual-recommendation
    │   ├── admin.ts             # advance-day, rules, templates, asset classes, thresholds
    │   └── audit.ts             # queryAuditLog
    ├── auth/                    # Session handling
    │   ├── AuthContext.tsx      # Token + role state, localStorage persistence, session restore via /api/auth/me
    │   ├── ProtectedRoute.tsx   # Role guard wrapper; redirects unauthenticated users to /login
    │   └── roleRedirect.ts      # Role → landing-route mapping (E2-S3 AC1)
    ├── types/                   # TypeScript mirrors of the backend contracts
    │   ├── entities.ts          # The 14 entities + RebalancingThreshold, identical snake_case field names (E1-S1 AC5)
    │   └── api.ts               # Request/response DTOs and the error envelope
    ├── lib/                     # Framework-free helpers
    │   ├── money.ts             # Fixed-point parse/format/compare; integer basis-point arithmetic (NFR-01)
    │   └── format.ts            # Date, enum-label and percentage display formatting
    ├── components/              # Shared presentational components
    │   ├── Layout.tsx           # Page frame with role-aware navigation
    │   ├── NavBar.tsx           # Persistent navigation links per role
    │   ├── DataTable.tsx        # Semantic table used by holdings, goals, audit, customer list
    │   ├── LabeledField.tsx     # label/input pairing with for/id association (accessibility baseline)
    │   ├── Modal.tsx            # Accessible dialog — used by the manual-recommendation modal
    │   ├── EmptyState.tsx       # Explicit empty-state messaging (E6-S5 AC3, E8-S4 AC4)
    │   └── ErrorMessage.tsx     # Inline error rendering from the API error envelope
    ├── pages/
    │   ├── Login.tsx            # Shared login screen with role-based redirect
    │   ├── customer/
    │   │   ├── Dashboard.tsx    # Customer landing; the ONE screen with a responsive breakpoint (BRD §5.3)
    │   │   ├── Questionnaire.tsx# Risk-profile form with per-question validation
    │   │   ├── RiskResult.tsx   # Assigned risk-band display
    │   │   ├── Allocation.tsx   # Recommended allocation view
    │   │   ├── Holdings.tsx     # Holdings and per-asset-class drift
    │   │   ├── Goals.tsx        # Goal list, create/edit form, progress display
    │   │   └── Rebalancing.tsx  # Pending recommendations with accept/dismiss
    │   ├── advisor/
    │   │   ├── CustomerList.tsx # Customer list with current risk band
    │   │   ├── CustomerDetail.tsx # Drill-in: holdings, goals, allocation, override history
    │   │   ├── OverrideForm.tsx # Risk-band override form (reason required)
    │   │   └── ManualRecommendationModal.tsx # Modal on the drill-in view — NOT a route (BRD §5.1)
    │   ├── admin/
    │   │   ├── AdminHome.tsx    # Admin landing with advance-a-day trigger
    │   │   ├── RuleEditor.tsx   # Questionnaire + scoring editor, ≥6-question publish gate
    │   │   ├── TemplateEditor.tsx # Allocation editor with live sum-to-100 running total
    │   │   ├── AssetClasses.tsx # Asset-class master list, create/edit
    │   │   └── ThresholdEditor.tsx # Publish a new RebalancingThreshold version
    │   └── compliance/
    │       └── AuditLog.tsx     # Read-only filterable audit table — no mutating control anywhere
    ├── styles/
    │   └── global.css           # Plain CSS, neutral palette; no design system (BRD §12)
    └── test/
        └── setup.ts             # vitest + Testing Library setup, MSW-style fetch stubbing
```

**Test placement.** Component and hook tests are colocated as `*.test.tsx` / `*.test.ts` next to the file under test (e.g. `src/pages/customer/Goals.test.tsx`). `src/test/setup.ts` holds only global setup.

---

## 4. Directory-to-Layer Mapping

The `check-architecture` hook resolves each file to a layer by directory and rejects an import that flows the wrong way.

| Directory | Layer | May import from |
|---|---|---|
| `backend/src/types/` | Types | stdlib, pydantic, other `types` modules |
| `backend/src/core/` | Config | `types` |
| `backend/src/db/`, `backend/src/domain/*/repository.py`, `*/threshold_repository.py` | Repository | `types`, `core`, `db` |
| `backend/src/domain/*/service.py` and pure helpers (`scoring.py`, `drift.py`, `engine.py`, `horizon.py`, `progress.py`) | Service | `types`, `core`, any repository, other services |
| `backend/src/app/` | API | `types`, `core`, services |
| `frontend/src/` | UI | HTTP only, through `frontend/src/api/` |

Two rules the hook enforces that are easy to violate accidentally: a **router may not import a repository**, and a **service may not raise `HTTPException`** (`system-design.md` §2.1).

---

## 5. Files That Are Never Committed

`.gitignore` covers, at minimum:

```
backend/.env
backend/*.db
backend/.venv/
backend/.pytest_cache/
backend/htmlcov/
backend/.coverage
frontend/.env
frontend/node_modules/
frontend/dist/
frontend/coverage/
```

`.env.example` **is** committed in both `backend/` and `frontend/`; the real `.env` files never are. The `protect-env` and `detect-secrets` hooks enforce this on write and on commit (`deployment.md` §5).
