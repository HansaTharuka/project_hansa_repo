# Deployment — WealthWise

Deployment, CI/CD, secrets and rollback for the WealthWise capstone. Scope is fixed by `project-manifest.json` (`deployment.method = "local-dev-servers"`) and BRD §5.2, which places production deployment explicitly out of scope.

---

## 1. Environments

**There is exactly one environment: local development.**

| Environment | Status |
|---|---|
| **dev (local)** | The only environment. Two processes on the developer's / evaluator's machine plus one SQLite file |
| staging | **Does not exist.** Explicitly out of scope per BRD §5.2 ("Production deployment, secret management, multi-region") |
| production | **Does not exist.** Same exclusion |

This is stated plainly rather than sketched speculatively. Inventing a staging or production topology would create specification surface that no story implements, no test covers, and no rubric criterion rewards — and it would contradict the BRD. If the project were ever taken further, the honest starting point is section 7's note on what would have to change, not a fictional pipeline described here as though it existed.

### 1.1 Local topology

| Component | Command (from repo root) | Address |
|---|---|---|
| Backend | `cd backend && uv run uvicorn app.main:app --reload` | `http://localhost:8000` |
| Frontend | `cd frontend && npm run dev` | `http://localhost:5173` |
| Database | — (created by `alembic upgrade head`) | `backend/wealthwise.db` |
| Health probe | `curl http://localhost:8000/health` | 200 within 1s of startup (NFR-07) |

These are the literal commands in `project-manifest.json` → `verification.local.start_commands`. They must not drift; the evaluator harness invokes them verbatim and polls `verification.health_check.url` with 5 retries at 2-second backoff.

**CORS:** the backend allows origin `http://localhost:5173` only. The Vite dev server does not proxy — the SPA calls `http://localhost:8000` directly using `VITE_API_BASE_URL`.

### 1.2 First-run setup

```bash
# Backend
cd backend
cp .env.example .env            # then fill in JWT_SECRET
uv sync                         # install locked dependencies
uv run alembic upgrade head     # create all 15 tables (idempotent)
uv run python -m db.seed        # load synthetic seed data (idempotent)
uv run uvicorn app.main:app --reload

# Frontend (separate shell)
cd frontend
cp .env.example .env
npm ci                          # install from package-lock.json
npm run dev
```

Both `alembic upgrade head` and the seed loader are idempotent (E1-S3 AC5, E6-S1 AC2), so re-running either against an existing database is safe.

### 1.3 Database lifecycle

`backend/wealthwise.db` is a git-ignored local artefact, not a deployed asset. A full reset is `rm backend/wealthwise.db && uv run alembic upgrade head && uv run python -m db.seed`. All data is synthetic (Synthetic-Data Rule) — no real customer, account or market data exists anywhere in the repository.

---

## 2. Infrastructure as Code

**None, deliberately.**

There is no Terraform, no Pulumi, no CloudFormation, no Helm chart, no Dockerfile, and no docker-compose file. The justification is not brevity — it is that there is nothing to provision:

- No cloud account, VPC, load balancer, DNS record or TLS certificate is involved.
- The database is a file created by a migration command, not a managed service that needs sizing, backup policy or network rules.
- The two processes run from the source tree with `--reload`; there is no build artefact to ship, no image registry, no orchestrator to schedule onto.
- `project-manifest.json` pins `deployment.method` to `local-dev-servers`, and BRD §5.2 excludes production deployment. IaC would describe infrastructure that the specification says will never exist.

What replaces IaC as the reproducibility mechanism: **locked dependency graphs** (`backend/uv.lock`, `frontend/package-lock.json`, both committed), **declarative schema migrations** (`backend/alembic/versions/`), and **an idempotent seed loader**. Those three make a fresh checkout reproducible on any machine with Python 3.12 and Node installed, which is the whole reproducibility requirement this project has.

---

## 3. CI/CD Pipeline — GitLab CI

Defined in `.gitlab-ci.yml` at the repository root. GitLab CI is the only CI target (BRD §8); there is no GitHub Actions workflow.

The pipeline **verifies** — it does not deploy, because there is nowhere to deploy to (§1).

### 3.1 Stages

| # | Stage | Job(s) | Command | Blocking |
|---|---|---|---|---|
| 1 | `lint` | `lint:backend` | `uv run ruff check src tests` | Yes |
| | | `lint:frontend` | `npm run lint` (eslint) | Yes |
| 2 | `typecheck` | `typecheck:backend` | `uv run mypy src` (strict) | Yes |
| | | `typecheck:frontend` | `npm run typecheck` (`tsc --noEmit`) | Yes |
| 3 | `test` | `test:backend` | `uv run pytest --cov=src --cov-report=xml --cov-report=term` | Yes |
| | | `test:frontend` | `npm run test:coverage` (vitest) | Yes |
| 4 | `coverage-gate` | `coverage:gate` | Fails the pipeline if combined line coverage < **80%** (`execution.coverage_threshold`) or if coverage regresses against `coverage-baseline.txt` | Yes |
| 5 | `review` | `claude:review` | Claude Code Action — automated review of the merge request diff against `specs/` | Yes on merge requests |

Stages run in order; a failing stage stops the pipeline. `lint` and `typecheck` jobs within a stage run in parallel.

### 3.2 Migration-immutability check

An additional job in the `lint` stage enforces NFR-05 mechanically:

```
migrations:append-only
  script: fail if `git diff --name-status origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME`
          reports M (modified) or D (deleted) for any path under backend/alembic/versions/
```

Only `A` (added) is permitted under `backend/alembic/versions/`. A correction to a committed migration must be a *new* revision.

### 3.3 Claude Code Action

The `review` stage runs Claude Code against the merge-request diff with `specs/` as context, checking that the change matches its story's acceptance criteria, respects the layering contract, and introduces no float arithmetic in money/percentage paths. It posts findings as MR comments. It is advisory on the content of its findings but **blocking on completion** — the job must run and exit successfully for the MR to be mergeable, satisfying the PR-Only-Merge Rule.

### 3.4 Caching

`uv` cache keyed on `backend/uv.lock`; `npm` cache keyed on `frontend/package-lock.json`. Cache misses only slow the pipeline; they never change its result.

### 3.5 What CI does not do

No build artefact is published, no image is pushed, no environment is provisioned, no release is tagged automatically, and no deployment job exists. There is no `deploy` stage in `.gitlab-ci.yml`, and its absence is intentional.

---

## 4. Local Verification Before Push

The hooks in `hooks/` run these continuously during development, but the pre-push equivalent of the pipeline is:

```bash
cd backend  && uv run ruff check src tests && uv run mypy src && uv run pytest --cov=src
cd frontend && npm run lint && npm run typecheck && npm run test:coverage
```

The `pre-commit-gate` hook blocks a commit that fails lint, typecheck or secret detection. The `sprint-contract-gate` hook blocks `/build` until the relevant `sprint-contracts/{group-id}.json` has `approved: true`.

---

## 5. Secrets Management

Secret handling is scoped to what a local-dev capstone actually needs. BRD §5.2 puts production secret management out of scope; this section covers the local discipline that remains mandatory.

### 5.1 Where configuration lives

| File | Committed | Contents |
|---|---|---|
| `backend/.env.example` | **Yes** | Every required variable with a placeholder value (E1-S2 AC5) |
| `backend/.env` | **Never** | Real local values — git-ignored |
| `frontend/.env.example` | **Yes** | `VITE_API_BASE_URL=http://localhost:8000` |
| `frontend/.env` | **Never** | Real local values — git-ignored |

Backend variables: `DATABASE_URL`, `JWT_SECRET`, `JWT_ACCESS_TOKEN_EXPIRY_MINUTES` (default `60`), `DEFAULT_DRIFT_THRESHOLD_PERCENT` (default `5`, seeds `RebalancingThreshold` version 1 only — see `system-design.md` §6.1), `SEED_CSV_PATH`, `LOG_LEVEL`.

### 5.2 Enforcement

Three independent mechanisms, because a single one is easy to bypass by accident:

1. **`protect-env` hook** — refuses any write to a `.env` file, so no agent can create or modify one.
2. **`detect-secrets` hook** — runs pre-commit; blocks a commit containing anything shaped like a key, token or password. Also runs as a CI job so a bypassed local hook still fails the pipeline.
3. **`.gitignore`** — `backend/.env` and `frontend/.env` are ignored, so they cannot be staged accidentally.

### 5.3 Rules

- No secret value appears in source outside `backend/src/core/config.py`, which reads them from the environment and never contains a literal (E1-S2 AC4).
- A missing required variable raises a clear startup error rather than starting with `None` (E1-S2 AC2).
- `JWT_SECRET` is developer-generated locally (`openssl rand -hex 32`). There is no shared secret, no key-management service, no rotation procedure — with one local environment there is nothing to rotate between.
- Seeded account passwords are synthetic, documented in `backend/seed/demo_accounts.json` as bcrypt hashes, and are demo credentials by construction. They are safe to commit **because no real system accepts them** — which is only true while the Synthetic-Data Rule holds.
- `password_hash` and `access_token` are never logged (NFR-03); the logging redaction allowlist in `backend/src/core/logging.py` excludes them by default rather than by explicit removal.

### 5.4 CI variables

The Claude Code Action job requires an API key, supplied as a **masked, protected** GitLab CI/CD variable (`ANTHROPIC_API_KEY`) set in project settings. It is never written to the repository, never echoed in job logs, and is the only secret the pipeline consumes.

---

## 6. Rollback Procedure

Rollback here means restoring the local dev environment and the repository to a known-good state. There is no running production system to roll back and no traffic to shift.

### 6.1 Code rollback

```bash
git revert <sha>          # preferred — preserves history, produces a reviewable MR
git revert -m 1 <merge-sha>   # for a merge commit
```

`git revert`, never `git reset --hard` on a shared branch, and never a force-push: the PR-Only-Merge Rule means every change including a revert goes through a merge request.

### 6.2 Schema rollback

```bash
cd backend
uv run alembic downgrade -1          # step back one revision
uv run alembic downgrade <revision>  # or to a specific revision
```

Two constraints on this:

- **The migration file itself is never deleted.** `downgrade` runs the revision's own `downgrade()` function; the revision stays in `alembic/versions/` (NFR-05, `system-design.md` §6.3).
- **`downgrade` is a local-dev convenience, not a data-safe operation.** Dropping a table drops its rows. Because all data is synthetic and reproducible from the seed loader, that is acceptable here and would not be in a real deployment.

Every revision must therefore implement a working `downgrade()`, and any revision altering an existing table must use `op.batch_alter_table` — SQLite cannot drop or retype a column in place.

### 6.3 Full environment reset

When schema and code have diverged badly, the fastest recovery is a rebuild rather than a stepwise downgrade:

```bash
cd backend
rm wealthwise.db
uv run alembic upgrade head
uv run python -m db.seed
```

This is the routine recovery path for local dev. It takes seconds and produces a byte-for-byte reproducible database because the seed data is deterministic.

### 6.4 Dependency rollback

`uv.lock` and `package-lock.json` are committed, so reverting the commit that changed a lock file and re-running `uv sync` / `npm ci` restores the exact previous dependency graph.

---

## 7. If This Were Ever Taken to Production

Out of scope, and listed only so the boundary is explicit rather than implied — none of this is built, and no story covers it:

- SQLite would need to be replaced by a server database; the `Decimal`-as-minor-units convention would map to `NUMERIC(18,2)`, which would simplify the fixed-point handling considerably.
- The JWT strategy would need refresh tokens, revocation and an httpOnly cookie rather than `localStorage` (`system-design.md` §6.2 explains why none of that is present now).
- `Alembic downgrade` would stop being an acceptable rollback for anything destructive; forward-fix migrations plus backups would replace it.
- Rate limiting on `/api/auth/login` would become mandatory (currently absent by decision — BRD §5.2).
- The two-service split rejected as Option B in BRD §7 would become worth revisiting, since it is the change that turns role separation from a controller-layer check into a network boundary.
