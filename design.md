# Claude Harness Engine v1 — Design Reference

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User / CI                            │
└─────────────────────┬───────────────────────────────────────┘
                      │ slash commands
┌─────────────────────▼───────────────────────────────────────┐
│                   Orchestrator (Claude)                      │
│  /brd → /spec → /design → /build → /test → /evaluate        │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
Planner   Generator  Evaluator  Test Eng  Security Rev
   │          │          │          │          │
   └──────────┴──────────┴──────────┴──────────┘
                         │
              ┌──────────▼──────────┐
              │     State Layer      │
              │  features.json       │
              │  claude-progress.txt │
              │  learned-rules.md    │
              │  failures.md         │
              │  iteration-log.md    │
              └──────────────────────┘
```

## Karpathy Ratchet Loop

```
        ┌──────────────────────────────────┐
        │         Build Feature            │
        └──────────────┬───────────────────┘
                       │
        ┌──────────────▼───────────────────┐
        │       Evaluate vs Design         │◄──────────┐
        └──────────────┬───────────────────┘           │
                       │                               │
              score ≥ threshold?                       │
                  /         \                          │
                Yes           No                       │
                 │             │                       │
        ┌────────▼──┐  ┌───────▼────────┐             │
        │  Proceed  │  │  Design Critic  │             │
        └───────────┘  │  suggests fix   │             │
                       └───────┬─────────┘             │
                               │                       │
                       ┌───────▼─────────┐             │
                       │  Generator      │─────────────┘
                       │  applies fix    │  (max 5 iterations)
                       └─────────────────┘
```

## Agent Roles

| Agent            | File                          | Responsibility                         |
|------------------|-------------------------------|----------------------------------------|
| Planner          | `.claude/agents/planner.md`   | Sprint planning, story breakdown       |
| Generator        | `.claude/agents/generator.md` | Feature implementation                 |
| Evaluator        | `.claude/agents/evaluator.md` | API + Playwright verification          |
| Design Critic    | `.claude/agents/design-critic.md` | Design scoring (Karpathy loop)     |
| UI Designer      | `.claude/agents/ui-designer.md`   | Mockups, design tokens             |
| Test Engineer    | `.claude/agents/test-engineer.md` | Test authoring and execution       |
| Security Reviewer| `.claude/agents/security-reviewer.md` | Vulnerability auditing         |

Project-specific additions (WealthWise, ≥2 required by capstone rubric §7.1) go in the same directories — e.g. `risk-profiler-agent`, `recommendation-engine-agent`, `rebalancing-agent`, `goal-tracker-agent`, `policy-version-validator-agent`.

## Hook Execution Order

| # | Hook                  | File                               | Trigger                        |
|---|-----------------------|-------------------------------------|--------------------------------|
| 1 | protect-env           | `hooks/protect-env.js`             | Any file write                 |
| 2 | detect-secrets        | `hooks/detect-secrets.js`          | Pre-commit                     |
| 3 | scope-directory       | `hooks/scope-directory.js`         | File access                    |
| 4 | lint-on-save          | `hooks/lint-on-save.js`            | File save (.py, .ts)           |
| 5 | typecheck             | `hooks/typecheck.js`               | File save (.py, .ts)           |
| 6 | check-function-length | `hooks/check-function-length.js`   | File save                      |
| 7 | check-file-length     | `hooks/check-file-length.js`       | File save                      |
| 8 | check-architecture    | `hooks/check-architecture.js`      | File save                      |
| 9 | sprint-contract-gate  | `hooks/sprint-contract-gate.js`    | Pre-build                      |
|10 | pre-commit-gate       | `hooks/pre-commit-gate.js`         | Pre-commit                     |
|11 | task-completed        | `hooks/task-completed.js`          | Post-task                      |
|12 | teammate-idle-check   | `hooks/teammate-idle-check.js`     | Periodic                       |

Project-specific additions (≥2 required, e.g. `allocation-sum-invariant-check.sh`, `template-immutability-check.sh`, `pii-redaction-check.sh`) run alongside these.

## State Files

| File                  | Purpose                                              |
|-----------------------|-------------------------------------------------------|
| `features.json`       | Feature registry with status tracking                |
| `claude-progress.txt` | Session progress and current pipeline position       |
| `learned-rules.md`    | Accumulated rules from past failures (ratchet memory)|
| `failures.md`         | Failure log for pattern analysis                     |
| `iteration-log.md`    | Evaluator iteration history per feature              |
| `eval-scores.json`    | Design scores per component per iteration            |
| `coverage-baseline.txt` | Test coverage baseline for regression detection   |

## Sprint Contract Format

A sprint contract (`sprint-contracts/{group-id}.json`) defines a unit of work:

```json
{
  "contract_id": "group-01",
  "group_name": "Risk Profile + Recommendation",
  "stories": ["risk-01", "risk-02", "rec-01"],
  "acceptance_criteria": ["AC-01", "AC-02", "AC-04"],
  "dependencies": [],
  "estimated_complexity": "medium",
  "approved": false
}
```

The sprint-contract-gate hook blocks `/build` until `approved: true`.

## Quality Principles

1. **Correctness first** — all tests must pass before a feature is considered done
2. **Type safety** — strict typing enforced by hooks on every save
3. **Layered architecture** — one-way dependency boundaries enforced by check-architecture hook
4. **Test coverage** — coverage gate enforced at ≥ 80%; regressions block merges
5. **Security by default** — secrets detection runs on every commit; env files are protected; PII/financial data never logged (NFR-03)
6. **Iterative improvement** — Karpathy ratchet ensures quality only moves forward

## WealthWise Domain Notes

- Fixed-point arithmetic only for money/percentages/drift (NFR-01) — no floats.
- Risk-band assignments, recommendations, rebalancing actions, overrides: append-only (NFR-02).
- Allocation templates: versioned, immutable once published; in-flight customers stay pinned to their version (AC-10).
- Allocation percentages must sum to exactly 100 (AC-02) — enforce as both domain invariant and architecture test (NFR-08).
- Rebalancing triggers when `abs(current% - target%) > threshold` per asset class (AC-05, AC-06).
