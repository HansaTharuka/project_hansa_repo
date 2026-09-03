# Dependency Graph — WealthWise

Generated from `specs/brd/brd.md` via `/spec`. Groups are execution waves: every story in a group can be implemented in parallel once all groups before it are complete. No circular dependencies exist (validated programmatically during generation).

## Mermaid Graph

```mermaid
graph TD
    E1-S1[E1-S1<br/>Define core domain types and schemas for]
    E1-S2[E1-S2<br/>Application configuration and environmen]
    E1-S3[E1-S3<br/>Database engine, migrations, and seed-da]
    E1-S4[E1-S4<br/>Health-check endpoint and structured JSO]
    E2-S1[E2-S1<br/>Authentication service (bcrypt verificat]
    E2-S2[E2-S2<br/>Login API endpoint]
    E2-S3[E2-S3<br/>Login UI with role-based redirect]
    E3-S1[E3-S1<br/>Append-only audit log repository]
    E3-S2[E3-S2<br/>Central audit-writer service]
    E3-S3[E3-S3<br/>Audit log API (filterable, compliance-ro]
    E3-S4[E3-S4<br/>Compliance audit-log UI screen]
    E4-S1[E4-S1<br/>Risk-profile questionnaire and versioned]
    E4-S2[E4-S2<br/>Deterministic risk-band scoring service]
    E4-S3[E4-S3<br/>Risk-profile submission API]
    E4-S4[E4-S4<br/>Risk-profile questionnaire UI and result]
    E5-S1[E5-S1<br/>Versioned allocation-template repository]
    E5-S2[E5-S2<br/>Allocation recommendation service]
    E5-S3[E5-S3<br/>Recommendation API endpoint]
    E5-S4[E5-S4<br/>Recommended allocation UI view]
    E6-S1[E6-S1<br/>AssetClass and NavSnapshot repository pl]
    E6-S2[E6-S2<br/>NAV 'advance a day' refresh service]
    E6-S3[E6-S3<br/>Holdings and per-asset-class drift calcu]
    E6-S4[E6-S4<br/>Holdings/drift and advance-day admin API]
    E6-S5[E6-S5<br/>Holdings and drift UI view]
    E7-S1[E7-S1<br/>Goal and GoalProgressSnapshot repository]
    E7-S2[E7-S2<br/>Goal management service]
    E7-S3[E7-S3<br/>Goal progress recompute service triggere]
    E7-S4[E7-S4<br/>Goals API (CRUD and progress)]
    E7-S5[E7-S5<br/>Goals UI (list, create/edit, progress)]
    E8-S1[E8-S1<br/>RebalancingRecommendation repository]
    E8-S2[E8-S2<br/>Rebalancing engine service]
    E8-S3[E8-S3<br/>Rebalancing API (list, accept, dismiss)]
    E8-S4[E8-S4<br/>Rebalancing recommendations UI]
    E9-S1[E9-S1<br/>AdvisorOverride repository]
    E9-S2[E9-S2<br/>Advisor override and manual-recommendati]
    E9-S3[E9-S3<br/>Advisor API (customer list, drill-in, ov]
    E9-S4[E9-S4<br/>Advisor UI (customer list, drill-in, ove]
    E10-S1[E10-S1<br/>Versioned rule/template publish reposito]
    E10-S2[E10-S2<br/>Admin publish service]
    E10-S3[E10-S3<br/>Admin API (publish rule/template version]
    E10-S4[E10-S4<br/>Admin UI (rule editor, template editor, ]
    E1-S1 --> E1-S3
    E1-S2 --> E1-S3
    E1-S2 --> E1-S4
    E1-S3 --> E1-S4
    E1-S3 --> E2-S1
    E2-S1 --> E2-S2
    E2-S2 --> E2-S3
    E1-S3 --> E3-S1
    E3-S1 --> E3-S2
    E3-S2 --> E3-S3
    E2-S2 --> E3-S3
    E3-S3 --> E3-S4
    E2-S3 --> E3-S4
    E1-S3 --> E4-S1
    E4-S1 --> E4-S2
    E3-S2 --> E4-S2
    E4-S2 --> E4-S3
    E2-S2 --> E4-S3
    E4-S3 --> E4-S4
    E2-S3 --> E4-S4
    E1-S3 --> E5-S1
    E5-S1 --> E5-S2
    E4-S2 --> E5-S2
    E3-S2 --> E5-S2
    E5-S2 --> E5-S3
    E2-S2 --> E5-S3
    E5-S3 --> E5-S4
    E2-S3 --> E5-S4
    E1-S3 --> E6-S1
    E6-S1 --> E6-S2
    E6-S1 --> E6-S3
    E6-S2 --> E6-S4
    E6-S3 --> E6-S4
    E2-S2 --> E6-S4
    E6-S4 --> E6-S5
    E2-S3 --> E6-S5
    E1-S3 --> E7-S1
    E7-S1 --> E7-S2
    E7-S1 --> E7-S3
    E6-S2 --> E7-S3
    E7-S2 --> E7-S4
    E7-S3 --> E7-S4
    E2-S2 --> E7-S4
    E7-S4 --> E7-S5
    E2-S3 --> E7-S5
    E1-S3 --> E8-S1
    E6-S3 --> E8-S2
    E8-S1 --> E8-S2
    E3-S2 --> E8-S2
    E8-S2 --> E8-S3
    E2-S2 --> E8-S3
    E8-S3 --> E8-S4
    E2-S3 --> E8-S4
    E1-S3 --> E9-S1
    E9-S1 --> E9-S2
    E4-S2 --> E9-S2
    E3-S2 --> E9-S2
    E9-S2 --> E9-S3
    E2-S2 --> E9-S3
    E9-S3 --> E9-S4
    E2-S3 --> E9-S4
    E4-S1 --> E10-S1
    E5-S1 --> E10-S1
    E10-S1 --> E10-S2
    E3-S2 --> E10-S2
    E10-S2 --> E10-S3
    E2-S2 --> E10-S3
    E10-S3 --> E10-S4
    E2-S3 --> E10-S4
```

## Execution Groups

### Group A

No dependencies — can start immediately, fully parallel.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E1-S1 | Define core domain types and schemas for all entities | Types | — |
| E1-S2 | Application configuration and environment settings | Config | — |

### Group B

Depends only on Group A.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E1-S3 | Database engine, migrations, and seed-data repository | Repository | E1-S1, E1-S2 |

### Group C

Depends only on Groups A, B.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E1-S4 | Health-check endpoint and structured JSON request logging | API | E1-S2, E1-S3 |
| E2-S1 | Authentication service (bcrypt verification, JWT issuance) | Service | E1-S3 |
| E3-S1 | Append-only audit log repository | Repository | E1-S3 |
| E4-S1 | Risk-profile questionnaire and versioned scoring-rule repository | Repository | E1-S3 |
| E5-S1 | Versioned allocation-template repository | Repository | E1-S3 |
| E6-S1 | AssetClass and NavSnapshot repository plus seed CSV loader | Repository | E1-S3 |
| E7-S1 | Goal and GoalProgressSnapshot repository | Repository | E1-S3 |
| E8-S1 | RebalancingRecommendation repository | Repository | E1-S3 |
| E9-S1 | AdvisorOverride repository | Repository | E1-S3 |

### Group D

Depends only on Groups A, B, C.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E2-S2 | Login API endpoint | API | E2-S1 |
| E3-S2 | Central audit-writer service | Service | E3-S1 |
| E6-S2 | NAV 'advance a day' refresh service | Service | E6-S1 |
| E6-S3 | Holdings and per-asset-class drift calculation service | Service | E6-S1 |
| E7-S2 | Goal management service | Service | E7-S1 |
| E10-S1 | Versioned rule/template publish repository | Repository | E4-S1, E5-S1 |

### Group E

Depends only on Groups A, B, C, D.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E2-S3 | Login UI with role-based redirect | UI | E2-S2 |
| E3-S3 | Audit log API (filterable, compliance-role-only) | API | E3-S2, E2-S2 |
| E4-S2 | Deterministic risk-band scoring service | Service | E4-S1, E3-S2 |
| E6-S4 | Holdings/drift and advance-day admin API | API | E6-S2, E6-S3, E2-S2 |
| E7-S3 | Goal progress recompute service triggered on NAV refresh | Service | E7-S1, E6-S2 |
| E8-S2 | Rebalancing engine service | Service | E6-S3, E8-S1, E3-S2 |
| E10-S2 | Admin publish service | Service | E10-S1, E3-S2 |

### Group F

Depends only on Groups A, B, C, D, E.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E3-S4 | Compliance audit-log UI screen | UI | E3-S3, E2-S3 |
| E4-S3 | Risk-profile submission API | API | E4-S2, E2-S2 |
| E5-S2 | Allocation recommendation service | Service | E5-S1, E4-S2, E3-S2 |
| E6-S5 | Holdings and drift UI view | UI | E6-S4, E2-S3 |
| E7-S4 | Goals API (CRUD and progress) | API | E7-S2, E7-S3, E2-S2 |
| E8-S3 | Rebalancing API (list, accept, dismiss) | API | E8-S2, E2-S2 |
| E9-S2 | Advisor override and manual-recommendation service | Service | E9-S1, E4-S2, E3-S2 |
| E10-S3 | Admin API (publish rule/template version, asset-class CRUD) | API | E10-S2, E2-S2 |

### Group G

Depends only on Groups A, B, C, D, E, F.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E4-S4 | Risk-profile questionnaire UI and result screen | UI | E4-S3, E2-S3 |
| E5-S3 | Recommendation API endpoint | API | E5-S2, E2-S2 |
| E7-S5 | Goals UI (list, create/edit, progress) | UI | E7-S4, E2-S3 |
| E8-S4 | Rebalancing recommendations UI | UI | E8-S3, E2-S3 |
| E9-S3 | Advisor API (customer list, drill-in, override, manual-rec log) | API | E9-S2, E2-S2 |
| E10-S4 | Admin UI (rule editor, template editor, asset-class master) | UI | E10-S3, E2-S3 |

### Group H

Depends only on Groups A, B, C, D, E, F, G.

| Story ID | Title | Layer | Depends On |
|---|---|---|---|
| E5-S4 | Recommended allocation UI view | UI | E5-S3, E2-S3 |
| E9-S4 | Advisor UI (customer list, drill-in, override form, manual-rec modal) | UI | E9-S3, E2-S3 |
