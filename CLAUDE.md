# WealthWise

Robo-Advisory & Portfolio Recommendation Platform — deterministic, rule-based risk profiling, portfolio allocation, drift detection, and rebalancing for retail investors. BFS Wealth Management (Business Case BC-AINE-008). Rule-based only, no ML. All production code agent-generated.

## Quick Reference

**Backend:** `cd backend && uv run pytest -x -q` | `uv run ruff check --fix .` | `uv run mypy src/`
**Frontend:** `cd frontend && npm test` | `npm run lint` | `npm run typecheck`
**Full stack:** `cd backend && uv run uvicorn app.main:app --reload` (terminal 1), `cd frontend && npm run dev` (terminal 2). See init.sh.

## Architecture

Strict layered architecture: Types → Config → Repository → Service → API → UI.
One-way dependencies only. See `.claude/architecture.md` for full rules.

## Where to Find Things

| What | Where |
|------|-------|
| Architecture rules | `.claude/architecture.md` |
| Quality principles | `.claude/skills/code-gen/SKILL.md` |
| Testing patterns | `.claude/skills/testing/SKILL.md` |
| Evaluation rubric | `.claude/skills/evaluation/SKILL.md` |
| Sprint contract format | `.claude/skills/evaluation/references/contract-schema.json` |
| Playwright patterns | `.claude/skills/evaluation/references/playwright-patterns.md` |
| Human control knobs | `.claude/program.md` |
| Session recovery | `claude-progress.txt` |
| Feature tracking | `features.json` |
| Learned rules | `.claude/state/learned-rules.md` |
| Business case | `docs/business-case.md` |
| App-level spec | `specs/app_spec.md` |
| Domain rules | `src/domain/` |

## Pipeline Commands

| Command | Purpose |
|---------|---------|
| `/brd` | Socratic interview → BRD |
| `/spec` | BRD → stories + features.json |
| `/design` | Architecture + schemas + mockups |
| `/build` | Full 8-phase pipeline |
| `/auto` | Autonomous ratcheting loop |
| `/implement` | Code gen with agent teams |
| `/evaluate` | Run app, verify contract |
| `/review` | Evaluator + security review |
| `/test` | Test plan + Playwright E2E |
| `/deploy` | Docker Compose + init.sh |

## Code Style

- TDD mandatory: test first, then implement
- 100% meaningful coverage target, 80% floor
- Functions < 50 lines, files < 300 lines
- Static typing everywhere (zero `any`)
- Fixed-point arithmetic for money/percentages — never floating-point (NFR-01)
- See `.claude/skills/code-gen/SKILL.md` for full rules

## Domain Rules (capstone-specific)

- No-Hand-Coding: production code, tests, migrations agent-generated only. Hand-edits limited to specs, CLAUDE.md, agent defs, hooks, skills.
- Spec-Is-Truth: spec/code disagreement → update spec, regenerate code.
- PR-Only Merge: no direct commits to `main`.
- Synthetic-Data only: no real/confidential data.
- Risk-band rules, allocation templates: versioned, append-only, immutable once published (NFR-05, AC-10).
- Allocation percentages must always sum to 100 (AC-02, NFR-08).
- PII/financial-position data never logged (NFR-03).

## Git

Branch: `<type>/<description>` (e.g., `feat/risk-profile`)
Commits: conventional format (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`)
Merges: `git merge --no-ff` to preserve PR history.
