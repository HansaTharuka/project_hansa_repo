# API Contracts — WealthWise

Base URL (local dev): `http://localhost:8000`
OpenAPI document: `specs/design/api-contracts.schema.json` (OpenAPI 3.0.3)

Every endpoint below is derived from an acceptance criterion in `specs/stories/`. Field names follow BRD section 9 exactly; the fixed-point transport convention is defined in `data-models.md` section 2 and summarised in section 3 below.

---

## 1. Conventions

### 1.1 Endpoint subheading format

Every endpoint is documented with the same eight fields, in the same order:

**Story · Auth · Rate limit · Request · Success · Errors · Side effects · Notes**

### 1.2 Authentication

All endpoints except `GET /health` and `POST /api/auth/login` require:

```
Authorization: Bearer <jwt>
```

The token is a single 60-minute HS256 access token; there is no refresh flow (`system-design.md` §6.2). Claims: `sub` (user id, string), `role`, `exp`, `iat`, and `customer_id` for the `customer` role.

Authorisation is applied by one FastAPI dependency, `require_role(*roles)`, at the router layer (NFR-04):

| Situation | Status |
|---|---|
| No `Authorization` header, or malformed/unsigned/expired token | **401** |
| Valid token, role not in the endpoint's allowed set | **403** |
| Valid token, correct role, but the resource belongs to another customer | **404** (see D12 in `system-design.md` §10 — a 403 would confirm the record exists) |

**Customer scoping:** for customer-role endpoints the `customer_id` is always taken from the token, never from a query parameter or body. There is no endpoint that lets a customer name another customer's id.

### 1.3 Rate limits

**None on any endpoint — out of scope per BRD §5.2.** This includes `POST /api/auth/login`; no throttling, lockout, or backoff is implemented. Stated explicitly so the absence reads as a decision.

### 1.4 Error envelope

Every non-2xx response uses one shape:

```json
{
  "error": {
    "code": "TEMPLATE_SUM_INVALID",
    "message": "Allocation percentages must sum to exactly 100.",
    "details": { "sum_bps": 9900 }
  }
}
```

`details` is optional and always an object when present. Services raise domain exceptions; a single handler module maps them to status codes — routers never construct status codes ad hoc.

| Status | Meaning | Representative `code` values |
|---|---|---|
| 400 | Malformed query parameter that Pydantic cannot coerce (e.g. unparseable date) | `INVALID_QUERY_PARAMETER` |
| 401 | Missing / invalid / expired credentials | `INVALID_CREDENTIALS`, `TOKEN_MISSING`, `TOKEN_EXPIRED`, `TOKEN_INVALID` |
| 403 | Authenticated but not permitted | `ROLE_NOT_PERMITTED`, `KYC_NOT_VERIFIED` |
| 404 | Resource absent, or not visible to this actor | `CUSTOMER_NOT_FOUND`, `NO_RISK_BAND_ASSIGNMENT`, `GOAL_NOT_FOUND`, `RECOMMENDATION_NOT_FOUND` |
| 405 | Method not registered on a registered path | `METHOD_NOT_ALLOWED` |
| 409 | Conflict with existing state | `VERSION_CONFLICT`, `ALREADY_RESOLVED`, `DAY_ALREADY_ADVANCED`, `DUPLICATE_ASSET_CLASS_CODE` |
| 422 | Body/params well-formed but semantically invalid | `VALIDATION_ERROR`, `INCOMPLETE_QUESTIONNAIRE`, `TEMPLATE_SUM_INVALID`, `QUESTIONNAIRE_TOO_SHORT`, `REASON_REQUIRED`, `NOTE_REQUIRED` |
| 500 | Unhandled | `INTERNAL_ERROR` (generic message; correlation id returned for log lookup) |

### 1.5 Headers

| Header | Direction | Notes |
|---|---|---|
| `Authorization: Bearer <jwt>` | request | All endpoints except `/health` and login |
| `X-Request-ID` | request (optional) / response (always) | Correlation id (NFR-06). Generated if absent |
| `Content-Type: application/json` | both | The only media type in use |

### 1.6 Pagination

Only `GET /api/audit` is paginated (`limit`, `offset`, default `limit = 50`, max `200`), because it is the only unbounded collection. All other collections are bounded by a single customer's data or by seed-scale master data and return a plain array.

---

## 2. Endpoint Index

| # | Method | Path | Roles | Story |
|---|---|---|---|---|
| 1 | GET | `/health` | public | E1-S4 |
| 2 | POST | `/api/auth/login` | public | E2-S2 |
| 3 | GET | `/api/auth/me` | any authenticated | E2-S3 |
| 4 | GET | `/api/risk-profile/questionnaire` | customer | E4-S3, E4-S4 |
| 5 | POST | `/api/risk-profile/submit` | customer | E4-S3 |
| 6 | GET | `/api/risk-profile/latest` | customer | E4-S3 |
| 7 | GET | `/api/recommendation` | customer | E5-S3 |
| 8 | GET | `/api/holdings` | customer | E6-S4 |
| 9 | POST | `/api/goals` | customer | E7-S4 |
| 10 | GET | `/api/goals` | customer | E7-S4 |
| 11 | PATCH | `/api/goals/{goal_id}` | customer | E7-S4 |
| 12 | GET | `/api/goals/{goal_id}/progress` | customer | E7-S4 |
| 13 | GET | `/api/rebalancing` | customer | E8-S3 |
| 14 | POST | `/api/rebalancing/{recommendation_id}/accept` | customer | E8-S3 |
| 15 | POST | `/api/rebalancing/{recommendation_id}/dismiss` | customer | E8-S3 |
| 16 | GET | `/api/advisor/customers` | advisor | E9-S3 |
| 17 | GET | `/api/advisor/customers/{customer_id}` | advisor | E9-S3 |
| 18 | POST | `/api/advisor/customers/{customer_id}/override` | advisor | E9-S3 |
| 19 | POST | `/api/advisor/customers/{customer_id}/manual-recommendation` | advisor | E9-S3 |
| 20 | POST | `/api/admin/advance-day` | admin | E6-S4 |
| 21 | GET | `/api/admin/risk-band-rules` | admin | E10-S3, E10-S4 |
| 22 | POST | `/api/admin/risk-band-rules` | admin | E10-S3 |
| 23 | GET | `/api/admin/allocation-templates` | admin | E10-S3 |
| 24 | POST | `/api/admin/allocation-templates` | admin | E10-S3 |
| 25 | GET | `/api/admin/asset-classes` | admin | E10-S3, E10-S4 |
| 26 | POST | `/api/admin/asset-classes` | admin | E10-S3 |
| 27 | PATCH | `/api/admin/asset-classes/{asset_class_id}` | admin | E10-S1 |
| 28 | GET | `/api/admin/rebalancing-thresholds` | admin | design §6.1 |
| 29 | POST | `/api/admin/rebalancing-thresholds` | admin | design §6.1 |
| 30 | GET | `/api/audit` | compliance | E3-S3 |

---

## 3. Value Representation

| Kind | JSON type | Example | Rule |
|---|---|---|---|
| Money | string | `"25000.00"` | Exactly 2 decimals, `.` separator, no thousands separator, no currency symbol |
| Percent / drift | string | `"60.00"`, `"-7.25"` | Exactly 2 decimals, may be negative for drift |
| Units | string | `"12.3456"` | Exactly 4 decimals |
| Threshold | integer + string | `"threshold_bps": 500`, `"threshold_percent": "5.00"` | `threshold_bps` is canonical |
| Timestamp | string | `"2026-09-03T10:15:00Z"` | ISO-8601 UTC, `Z` suffix |
| Date | string | `"2026-09-04"` | `YYYY-MM-DD` |
| Enum | string | `"MODERATE"` | Exact literal from `data-models.md` |

**Money and percentages are never JSON numbers** — see `data-models.md` §2 rule 1 (NFR-01).

---

## 4. System

### 4.1 `GET /health`

- **Story:** E1-S4 (AC1, AC4, AC5) · NFR-07
- **Auth:** public — no token required.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** no headers, params, or body.
- **Success — 200:**
  ```json
  { "status": "ok", "database": "connected", "version": "1.0.0" }
  ```
  Must be returned within 1 second of the application completing startup (NFR-07), and returns 200 even when the database contains only seed data.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 503 | `DATABASE_UNAVAILABLE` | The connectivity probe fails; body `{"status":"degraded","database":"unavailable"}` |
- **Side effects:** none. Never writes an audit entry, never logs PII.
- **Notes:** this is the URL in `project-manifest.json`'s `verification.health_check`. It is **not** under `/api` — the path is exactly `/health`.

---

## 5. Authentication

### 5.1 `POST /api/auth/login`

- **Story:** E2-S2 (AC1–AC4), E2-S1
- **Auth:** public.
- **Rate limit:** none — out of scope per BRD §5.2 (no lockout, no throttle).
- **Request:**
  ```json
  { "email": "customer03@wealthwise.test", "password": "..." }
  ```
  Both fields required, non-empty strings. `email` is compared case-insensitively.
- **Success — 200:**
  ```json
  { "access_token": "eyJhbGciOi...", "token_type": "bearer", "role": "customer", "expires_in": 3600 }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `INVALID_CREDENTIALS` | Unknown email **or** wrong password — deliberately indistinguishable (E2-S1 AC2). No token in the body |
  | 422 | `VALIDATION_ERROR` | `email` or `password` missing or empty (E2-S2 AC3) |
- **Side effects:** none persisted. The request log line records the outcome and role, never the password or email (NFR-03).
- **Notes:** the response never contains `password_hash` or any credential material (E2-S2 AC4). There is no registration, password-reset, refresh, or logout endpoint — logout is a client-side token discard.

### 5.2 `GET /api/auth/me`

- **Story:** E2-S3 (AC5) — session restore on page refresh. The one endpoint added beyond those literally named in the stories (`system-design.md` D14).
- **Auth:** any authenticated role (`customer`, `advisor`, `admin`, `compliance`).
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `Authorization` header only.
- **Success — 200:**
  ```json
  { "user_id": 3, "email": "customer03@wealthwise.test", "role": "customer", "customer_id": 3 }
  ```
  `customer_id` is `null` for non-customer roles.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` / `TOKEN_EXPIRED` / `TOKEN_INVALID` | The SPA clears the stored token and routes to login |
- **Side effects:** none.
- **Notes:** makes E2-S3 AC5 server-verified rather than trusting client-side token inspection.

---

## 6. Risk Profiling (customer)

### 6.1 `GET /api/risk-profile/questionnaire`

- **Story:** E4-S4 (AC1) — the UI must render "all questions from the active `RiskBandRule` version"; E4-S1 AC2.
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `Authorization` header only.
- **Success — 200:**
  ```json
  {
    "rule_version": 1,
    "questions": [
      {
        "question_id": "Q1",
        "text": "What is your investment time horizon?",
        "options": [
          { "value": "lt_3y", "label": "Less than 3 years" },
          { "value": "3_7y",  "label": "3 to 7 years" },
          { "value": "gt_7y", "label": "More than 7 years" }
        ]
      }
    ]
  }
  ```
  At least 6 questions. **`points` are deliberately omitted** — the client must not be able to reverse-engineer or pre-compute the band.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | advisor / admin / compliance token |
  | 404 | `NO_ACTIVE_RULE` | No `RiskBandRule` has `is_active = true` (only reachable on an unseeded database) |
- **Side effects:** none.
- **Notes:** `rule_version` is echoed so the submit call can be correlated to the exact rule the customer answered against.

### 6.2 `POST /api/risk-profile/submit`

- **Story:** E4-S3 (AC1–AC3, AC5), E4-S2
- **Auth:** `customer` only (E4-S3 AC3).
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:**
  ```json
  { "answers": [ { "question_id": "Q1", "answer_value": "gt_7y" }, { "question_id": "Q2", "answer_value": "high" } ] }
  ```
  `answers` must contain exactly one entry for **every** `question_id` in the active questionnaire. `customer_id` is taken from the token and must not appear in the body.
- **Success — 201:**
  ```json
  { "assignment_id": 12, "risk_band": "MODERATE", "rule_version": 1, "assigned_at": "2026-09-03T10:15:00Z" }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated (E4-S3 AC5) |
  | 403 | `ROLE_NOT_PERMITTED` | advisor / admin / compliance token (E4-S3 AC3) |
  | 404 | `NO_ACTIVE_RULE` | No active rule version |
  | 422 | `INCOMPLETE_QUESTIONNAIRE` | Fewer answers than questions, a duplicate `question_id`, an unknown `question_id`, or an `answer_value` not among that question's options. **No `RiskBandAssignment` and no `RiskProfileAnswer` rows are written** (E4-S3 AC2, BRD §11) |
- **Side effects:** inserts one `RiskProfileAnswer` per answer, one `RiskBandAssignment` (append-only), and exactly one `AuditLogEntry` with `entity_type = "RiskBandAssignment"`, `action = "ASSIGN_RISK_BAND"` (E4-S2 AC4). All in one transaction.
- **Notes:** deterministic — the same answers always yield the same band (E4-S2 AC1). Resubmission inserts a new assignment; the previous one is never mutated (E4-S2 AC6).

### 6.3 `GET /api/risk-profile/latest`

- **Story:** E4-S3 (AC4), E4-S4 (AC5)
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `Authorization` header only.
- **Success — 200:**
  ```json
  { "assignment_id": 12, "customer_id": 3, "risk_band": "MODERATE", "rule_version": 1, "assigned_at": "2026-09-03T10:15:00Z" }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
  | 404 | `NO_RISK_BAND_ASSIGNMENT` | The customer has never been assigned a band (E4-S3 AC4) |
- **Side effects:** none.
- **Notes:** "latest" is `ORDER BY assigned_at DESC, id DESC LIMIT 1`, so an advisor override is reflected immediately.

---

## 7. Allocation Recommendation (customer)

### 7.1 `GET /api/recommendation`

- **Story:** E5-S3 (AC1–AC5), E5-S2
- **Auth:** `customer` only (E5-S3 AC3).
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** optional query `goal_id` (integer) to select the horizon from a specific goal. Omitted → the customer's highest-priority goal supplies the horizon; if the customer has no goals, the default horizon bucket `MEDIUM` is used.
- **Success — 200:**
  ```json
  {
    "risk_band": "MODERATE",
    "rule_version": 1,
    "template_version": 2,
    "horizon": "LONG",
    "allocations": [
      { "asset_class_id": 1, "asset_class_code": "EQ_DM",  "asset_class_name": "Developed-Market Equity", "percent": "40.00" },
      { "asset_class_id": 2, "asset_class_code": "FI_GOV", "asset_class_name": "Government Fixed Income", "percent": "35.00" },
      { "asset_class_id": 3, "asset_class_code": "CASH",   "asset_class_name": "Cash",                     "percent": "25.00" }
    ],
    "total_percent": "100.00",
    "generated_at": "2026-09-03T10:20:00Z"
  }
  ```
  `total_percent` is always exactly `"100.00"` (AC-02, E5-S3 AC1). `template_version` provides AC-10 traceability (E5-S3 AC4).
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated (E5-S3 AC5) |
  | 403 | `ROLE_NOT_PERMITTED` | advisor / admin / compliance (E5-S3 AC3) |
  | 404 | `NO_RISK_BAND_ASSIGNMENT` | No band assigned — **no default/fallback allocation is returned** (E5-S2 AC2, E5-S3 AC2) |
  | 404 | `GOAL_NOT_FOUND` | `goal_id` given but not owned by this customer |
  | 404 | `NO_ACTIVE_TEMPLATE` | No active `AllocationTemplate` for the band |
- **Side effects:** one `AuditLogEntry`, `entity_type = "AllocationRecommendation"`, `action = "GENERATE_ALLOCATION_RECOMMENDATION"` (E5-S2 AC3).
- **Notes:** horizon buckets are derived deterministically from `target_date` minus today — `SHORT` < 3 years, `MEDIUM` 3–7 years, `LONG` > 7 years. The same band + horizon always selects the same template (E5-S2 AC4).

---

## 8. Holdings and Drift (customer)

### 8.1 `GET /api/holdings`

- **Story:** E6-S4 (AC1, AC5), E6-S3, E6-S5
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `Authorization` header only.
- **Success — 200:**
  ```json
  {
    "as_of_date": "2026-09-04",
    "total_value": "100000.00",
    "threshold_bps": 500,
    "threshold_percent": "5.00",
    "holdings": [
      {
        "asset_class_id": 1, "asset_class_code": "EQ_DM", "asset_class_name": "Developed-Market Equity",
        "current_value": "48200.00", "current_percent": "48.20", "target_percent": "40.00",
        "drift_percent": "8.20", "exceeds_threshold": true
      },
      {
        "asset_class_id": 3, "asset_class_code": "CASH", "asset_class_name": "Cash",
        "current_value": "51800.00", "current_percent": "51.80", "target_percent": "60.00",
        "drift_percent": "-8.20", "exceeds_threshold": false
      }
    ]
  }
  ```
  A customer with no holdings returns **200** with `"holdings": []`, `"total_value": "0.00"`, `"as_of_date": null` — not an error (E6-S4 AC5, E6-S3 AC3).
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
- **Side effects:** none — drift is computed on read, never stored.
- **Notes:** `exceeds_threshold` is `abs(drift) > threshold`, **strictly greater** (E6-S3 AC4). `current_percent` values sum to exactly `"100.00"` when at least one asset is held (E6-S3 AC5); the residual bp is absorbed by the largest holding. Where the customer has no `RiskBandAssignment`, `target_percent` is `"0.00"` for every asset class and `exceeds_threshold` is `false`.

---

## 9. Goals (customer)

### 9.1 `POST /api/goals`

- **Story:** E7-S4 (AC1, AC2), E7-S2
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:**
  ```json
  { "target_amount": "250000.00", "target_date": "2032-06-30", "priority": 1 }
  ```
  `target_amount` money string > 0; `target_date` future date; `priority` integer 1–5. `customer_id` comes from the token.
- **Success — 201:**
  ```json
  { "id": 7, "customer_id": 3, "target_amount": "250000.00", "target_date": "2032-06-30", "priority": 1, "created_at": "2026-09-01T09:30:00Z", "updated_at": "2026-09-01T09:30:00Z", "percent_complete": null }
  ```
  `percent_complete` is `null` until the first `GoalProgressSnapshot` exists.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
  | 422 | `VALIDATION_ERROR` | `target_amount <= 0` (E7-S4 AC2, E7-S2 AC1), `target_date` in the past (E7-S2 AC2), `priority` outside 1–5, or a money string with the wrong scale |
- **Side effects:** inserts one `Goal`. Creating a second goal never removes or overwrites the first (E7-S2 AC3).
- **Notes:** no audit entry — goal CRUD is not in NFR-02's append-only set.

### 9.2 `GET /api/goals`

- **Story:** E7-S4 (AC3), E7-S5
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `Authorization` header only.
- **Success — 200:** array of goal objects, each shaped as in 9.1, with `percent_complete` populated from the latest `GoalProgressSnapshot` (or `null` if none). Ordered by `priority ASC, target_date ASC`.
  ```json
  [ { "id": 7, "customer_id": 3, "target_amount": "250000.00", "target_date": "2032-06-30", "priority": 1, "created_at": "2026-09-01T09:30:00Z", "updated_at": "2026-09-01T09:30:00Z", "percent_complete": "25.00" } ]
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
- **Side effects:** none.
- **Notes:** returns **only** the authenticated customer's goals — there is no query parameter capable of widening the scope (E7-S4 AC3).

### 9.3 `PATCH /api/goals/{goal_id}`

- **Story:** E7-S4 (AC5), E7-S2 (AC4, AC5)
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `goal_id` (integer). Body is a partial update; at least one field required:
  ```json
  { "priority": 3 }
  ```
  Updatable fields: `target_amount`, `target_date`, `priority`. `customer_id`, `created_at` and `id` are **not** updatable and are rejected if present.
- **Success — 200:** the full updated goal object (shape as 9.1). `created_at` is unchanged; `updated_at` moves (E7-S2 AC4).
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
  | 404 | `GOAL_NOT_FOUND` | Unknown id, **or** the goal belongs to another customer (E7-S2 AC5) |
  | 422 | `VALIDATION_ERROR` | Same rules as creation; empty body; attempt to set an immutable field |
- **Side effects:** updates the `Goal` row only. Existing `GoalProgressSnapshot` rows are never rewritten.
- **Notes:** editing `target_amount` changes future `percent_complete` values; historical snapshots keep the figure computed at their own `price_date`.

### 9.4 `GET /api/goals/{goal_id}/progress`

- **Story:** E7-S4 (AC4), E7-S3
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `goal_id` (integer).
- **Success — 200:** the ordered history of snapshots, oldest first.
  ```json
  {
    "goal_id": 7,
    "target_amount": "250000.00",
    "snapshots": [
      { "id": 80, "current_value": "50000.00", "percent_complete": "20.00", "snapshot_at": "2026-09-03T10:30:00Z", "price_date": "2026-09-03" },
      { "id": 88, "current_value": "62500.00", "percent_complete": "25.00", "snapshot_at": "2026-09-04T10:30:00Z", "price_date": "2026-09-04" }
    ]
  }
  ```
  A goal with no snapshots yet returns 200 with `"snapshots": []`.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
  | 404 | `GOAL_NOT_FOUND` | Unknown id or another customer's goal |
- **Side effects:** none.
- **Notes:** `percent_complete` is capped at `"200.00"` (`data-models.md` §4.8). Snapshots are created only by advance-a-day (11.1), never by this endpoint.

---

## 10. Rebalancing (customer)

### 10.1 `GET /api/rebalancing`

- **Story:** E8-S3 (AC1), E8-S4
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** optional query `status` ∈ `pending` | `accepted` | `dismissed`; default `pending`.
- **Success — 200:**
  ```json
  [
    {
      "recommendation_id": "b6f0c2a4-1d3e-4f58-9a71-0c2e5d8b7a10",
      "status": "pending",
      "generated_at": "2026-09-04T08:00:00Z",
      "resolved_at": null,
      "threshold_bps": 500,
      "proposed_actions": [
        { "asset_class_id": 1, "asset_class_code": "EQ_DM", "action": "SELL", "amount": "3200.00", "units": "24.1600", "drift_percent": "8.20" },
        { "asset_class_id": 3, "asset_class_code": "CASH",  "action": "BUY",  "amount": "3200.00", "units": "32.0000", "drift_percent": "-8.20" }
      ]
    }
  ]
  ```
  No pending recommendations → 200 with `[]` (E8-S4 AC4).
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
  | 400 | `INVALID_QUERY_PARAMETER` | `status` outside the enum |
- **Side effects:** none — recommendations are generated by advance-a-day, not by this read.
- **Notes:** the public `recommendation_id` (UUID) is used in paths, not the internal row `id`.

### 10.2 `POST /api/rebalancing/{recommendation_id}/accept`

- **Story:** E8-S3 (AC2, AC4, AC5)
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `recommendation_id` (UUID string). No body.
- **Success — 200:**
  ```json
  { "recommendation_id": "b6f0c2a4-1d3e-4f58-9a71-0c2e5d8b7a10", "status": "accepted", "resolved_at": "2026-09-04T09:12:00Z" }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-customer role |
  | 404 | `RECOMMENDATION_NOT_FOUND` | Unknown id, **or** it belongs to another customer (E8-S3 AC5) |
  | 409 | `ALREADY_RESOLVED` | Status is already `accepted` or `dismissed`; `resolved_at` is left unchanged (E8-S3 AC4, E8-S1 AC4) |
- **Side effects:** sets `status = "accepted"` and `resolved_at`; writes one `AuditLogEntry` (`action = "ACCEPT_REBALANCING_RECOMMENDATION"`). The row is never deleted and `proposed_actions_json` is never rewritten.
- **Notes:** accepting is a record of intent only — there is no brokerage integration (BRD §5.2), so no holdings are moved.

### 10.3 `POST /api/rebalancing/{recommendation_id}/dismiss`

- **Story:** E8-S3 (AC3, AC4, AC5)
- **Auth:** `customer`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `recommendation_id` (UUID string). No body.
- **Success — 200:** as 10.2 with `"status": "dismissed"`.
- **Errors:** identical table to 10.2.
- **Side effects:** sets `status = "dismissed"` and `resolved_at`; writes one `AuditLogEntry` (`action = "DISMISS_REBALANCING_RECOMMENDATION"`).
- **Notes:** dismissal is terminal — the same drift may produce a *new* recommendation on the next advance-a-day, with a new `recommendation_id`.

---

## 11. Advisor

All endpoints in this section: **`advisor` role only**. A `customer`-, `admin`- or `compliance`-role token returns **403** (E9-S3 AC5).

### 11.1 `GET /api/advisor/customers`

- **Story:** E9-S3 (AC1, AC5), E9-S4
- **Auth:** `advisor`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `Authorization` header only.
- **Success — 200:**
  ```json
  [ { "customer_id": 3, "email": "customer03@wealthwise.test", "risk_band": "MODERATE", "kyc_verified": true, "total_value": "100000.00", "goal_count": 2 } ]
  ```
  `risk_band` is `null` for a customer who has never completed the questionnaire.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | customer / admin / compliance token |
- **Side effects:** none.
- **Notes:** customers are identified by `email`; there is no name field on `Customer` (`data-models.md` §1.1).

### 11.2 `GET /api/advisor/customers/{customer_id}`

- **Story:** E9-S3 (AC2, AC5), E9-S4 (AC2)
- **Auth:** `advisor`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `customer_id` (integer).
- **Success — 200:** the full drill-in payload — holdings, goals and current allocation on one call, so the drill-in view needs no fan-out.
  ```json
  {
    "customer_id": 3,
    "email": "customer03@wealthwise.test",
    "kyc_verified": true,
    "risk_band": "MODERATE",
    "rule_version": 1,
    "holdings": { "as_of_date": "2026-09-04", "total_value": "100000.00", "threshold_bps": 500, "holdings": [] },
    "goals": [],
    "allocation": { "template_version": 2, "allocations": [], "total_percent": "100.00" },
    "override_history": [
      { "id": 4, "advisor_id": 11, "previous_band": "AGGRESSIVE", "new_band": "MODERATE", "reason": "Client reported imminent liquidity need", "note": null, "created_at": "2026-09-03T14:05:00Z" }
    ]
  }
  ```
  `allocation` is `null` when the customer has no `RiskBandAssignment`.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-advisor role |
  | 404 | `CUSTOMER_NOT_FOUND` | Unknown `customer_id` |
- **Side effects:** none — this read does **not** write an `AllocationRecommendation` audit entry, because the customer did not request a recommendation.
- **Notes:** `override_history` is ordered `created_at DESC` (E9-S1 AC3).

### 11.3 `POST /api/advisor/customers/{customer_id}/override`

- **Story:** E9-S3 (AC3, AC5), E9-S2, E9-S1 — AC-09
- **Auth:** `advisor`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `customer_id` (integer).
  ```json
  { "new_band": "CONSERVATIVE", "reason": "Client reported imminent liquidity need", "note": "Revisit after property sale completes." }
  ```
  `new_band` required enum; `reason` **required**, non-empty after trimming; `note` optional. `previous_band` and `advisor_id` are **server-derived** and rejected if supplied.
- **Success — 201:**
  ```json
  { "override_id": 4, "customer_id": 3, "previous_band": "MODERATE", "new_band": "CONSERVATIVE", "reason": "Client reported imminent liquidity need", "note": "Revisit after property sale completes.", "created_at": "2026-09-03T14:05:00Z", "assignment_id": 13, "risk_band": "CONSERVATIVE" }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-advisor role (E9-S3 AC5) |
  | 404 | `CUSTOMER_NOT_FOUND` | Unknown customer (E9-S2 AC5) |
  | 409 | `NO_PRIOR_ASSIGNMENT` | The customer has no `RiskBandAssignment`, so `previous_band` cannot be established (E9-S1 AC5) |
  | 422 | `REASON_REQUIRED` | `reason` missing, empty or whitespace-only — **no `AdvisorOverride` and no `RiskBandAssignment` row is written** (E9-S3 AC3, E9-S2 AC2) |
  | 422 | `VALIDATION_ERROR` | `new_band` not in the enum |
- **Side effects:** in one transaction — inserts an `AdvisorOverride`, inserts a **new** `RiskBandAssignment` with `new_band` and the active `rule_version`, and writes exactly one `AuditLogEntry` (`entity_type = "AdvisorOverride"`, `action = "OVERRIDE_RISK_BAND"`) (E9-S2 AC1, AC3).
- **Notes:** subsequent `GET /api/recommendation` calls for that customer use the overridden band immediately (E9-S2 AC1, E5-S4 AC5). Overriding to the same band is permitted and recorded — it is a documented advisory decision, not a no-op.

### 11.4 `POST /api/advisor/customers/{customer_id}/manual-recommendation`

- **Story:** E9-S3 (AC4, AC5), E9-S2 (AC4), E9-S4 (AC5) — resolves BRD §13's deferred modal-field question (`system-design.md` §6.4)
- **Auth:** `advisor`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `customer_id` (integer).
  ```json
  { "note": "Recommended increasing cash weighting ahead of the client's Q4 liquidity need." }
  ```
  **`note` is the only body field** — required, 1–2000 characters after trimming. `customer_id` comes from the path, `advisor_id` from the JWT `sub`, `created_at` from the server.
- **Success — 201:**
  ```json
  { "audit_entry_id": 512, "customer_id": 3, "advisor_id": 11, "note": "Recommended increasing cash weighting ahead of the client's Q4 liquidity need.", "created_at": "2026-09-03T14:10:00Z" }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-advisor role |
  | 404 | `CUSTOMER_NOT_FOUND` | Unknown customer |
  | 422 | `NOTE_REQUIRED` | `note` missing, empty, whitespace-only, or > 2000 characters |
- **Side effects:** writes exactly one `AuditLogEntry` — `entity_type = "ManualRecommendation"`, `entity_id = customer_id`, `actor_id = advisor_id`, `actor_role = "advisor"`, `action = "LOG_MANUAL_RECOMMENDATION"`, `details_json = {"note": "..."}`. **No new table** (`system-design.md` §6.4).
- **Notes:** the UI for this is a modal on the drill-in view, never a standalone route (BRD §5.1, E9-S4 AC5). The note appears on the compliance audit screen under `entity_type = ManualRecommendation`.

---

## 12. Admin

All endpoints in this section: **`admin` role only**. A `customer`-, `advisor`- or `compliance`-role token returns **403** (E10-S3 AC4, E6-S4 AC3).

### 12.1 `POST /api/admin/advance-day`

- **Story:** E6-S4 (AC2, AC3, AC4), E6-S2, E7-S3, E8-S2
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** no body.
- **Success — 200:**
  ```json
  {
    "price_date": "2026-09-04",
    "nav_snapshots_created": 6,
    "holdings_revalued": 24,
    "goal_snapshots_created": 12,
    "rebalancing_recommendations_created": 3
  }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | customer / advisor / compliance (E6-S4 AC3) |
  | 409 | `DAY_ALREADY_ADVANCED` | A second call for the same simulated day. **No duplicate `NavSnapshot` rows** — guaranteed by `UNIQUE(asset_class_id, price_date)` (E6-S4 AC4, E6-S2 AC2, BRD §11) |
- **Side effects**, in this fixed order, inside one transaction (`system-design.md` §5.3): insert one `NavSnapshot` per `AssetClass` for `max(price_date) + 1 day` → revalue every `Holding` → recompute drift → insert one `GoalProgressSnapshot` per active goal → evaluate rebalancing for every customer with holdings and `kyc_verified = true`, inserting `RebalancingRecommendation` rows and one `AuditLogEntry` each.
- **Notes:** manual trigger only — no scheduler, cron, or timer (E6-S2 AC4). Customers with `kyc_verified = false` are skipped for rebalancing but still receive NAV revaluation and goal snapshots.

### 12.2 `GET /api/admin/risk-band-rules`

- **Story:** E10-S4 (AC5) — version history refresh after publish; E4-S1 AC4
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** no parameters.
- **Success — 200:** all versions, active and superseded, ordered by `version ASC`.
  ```json
  [ { "id": 1, "version": 1, "questionnaire_json": { "questions": [] }, "scoring_rules_json": { "bands": [] }, "published_at": "2026-09-01T09:00:00Z", "is_active": false },
    { "id": 2, "version": 2, "questionnaire_json": { "questions": [] }, "scoring_rules_json": { "bands": [] }, "published_at": "2026-09-03T12:00:00Z", "is_active": true } ]
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
- **Side effects:** none.
- **Notes:** superseded versions remain individually queryable (E10-S1 AC5) — this is the read that demonstrates it. Unlike the customer questionnaire endpoint (6.1), the admin view **does** include each option's `points`.

### 12.3 `POST /api/admin/risk-band-rules`

- **Story:** E10-S3 (AC1, AC4), E10-S2 (AC2, AC3, AC4), E10-S1
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:**
  ```json
  {
    "questionnaire_json": { "questions": [ { "question_id": "Q1", "text": "...", "options": [ { "value": "lt_3y", "label": "...", "points": 1 } ] } ] },
    "scoring_rules_json": { "bands": [ { "risk_band": "CONSERVATIVE", "min_points": 6, "max_points": 13 }, { "risk_band": "MODERATE", "min_points": 14, "max_points": 22 }, { "risk_band": "AGGRESSIVE", "min_points": 23, "max_points": 30 } ] }
  }
  ```
  `version` is **server-assigned** (`max(version) + 1`) and rejected if supplied.
- **Success — 201:**
  ```json
  { "id": 2, "version": 2, "published_at": "2026-09-03T12:00:00Z", "is_active": true }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role (E10-S3 AC4) |
  | 409 | `VERSION_CONFLICT` | A concurrent publish already claimed the next version — the `UNIQUE(version)` constraint rejects the loser rather than overwriting (E10-S2 AC3, BRD §11) |
  | 422 | `QUESTIONNAIRE_TOO_SHORT` | Fewer than 6 questions (E10-S2 AC2) |
  | 422 | `VALIDATION_ERROR` | Duplicate `question_id`, a question with fewer than 2 options, non-integer `points`, or band ranges that overlap, leave a gap, or do not cover the min/max achievable point total |
- **Side effects:** inserts the new `RiskBandRule` with `is_active = true`, sets the prior active row's `is_active = false`, and writes one `AuditLogEntry` (`entity_type = "RiskBandRule"`, `action = "PUBLISH_RISK_BAND_RULE"`) (E10-S2 AC4). Existing rows' JSON is never mutated (E10-S1 AC3).
- **Notes:** customers already assigned under an earlier version stay pinned via `RiskBandAssignment.rule_version` (AC-10).

### 12.4 `GET /api/admin/allocation-templates`

- **Story:** E10-S3 (AC5), E10-S4 (AC5)
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** optional query `risk_band` ∈ `CONSERVATIVE` | `MODERATE` | `AGGRESSIVE`. Omitted → all bands.
- **Success — 200:** all versions for the band(s), active and superseded, ordered by `risk_band ASC, version ASC` (E10-S3 AC5).
  ```json
  [ { "id": 3, "version": 1, "risk_band": "CONSERVATIVE", "allocations": [ { "asset_class_id": 2, "asset_class_code": "FI_GOV", "percent": "70.00" }, { "asset_class_id": 3, "asset_class_code": "CASH", "percent": "30.00" } ], "total_percent": "100.00", "published_at": "2026-09-01T09:00:00Z", "is_active": false } ]
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
  | 400 | `INVALID_QUERY_PARAMETER` | `risk_band` outside the enum |
- **Side effects:** none.
- **Notes:** demonstrates in-flight pinning — a superseded version is still returned in full (E5-S1 AC4, E10-S1 AC5).

### 12.5 `POST /api/admin/allocation-templates`

- **Story:** E10-S3 (AC2, AC4), E10-S2 (AC1, AC3, AC4), E10-S1, E5-S1 — AC-02, AC-10
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:**
  ```json
  {
    "risk_band": "MODERATE",
    "allocations": [
      { "asset_class_id": 1, "percent": "40.00" },
      { "asset_class_id": 2, "percent": "35.00" },
      { "asset_class_id": 3, "percent": "25.00" }
    ]
  }
  ```
  Percentages are 2-dp strings; each `asset_class_id` must exist and appear at most once; `version` is server-assigned.
- **Success — 201:**
  ```json
  { "id": 7, "version": 3, "risk_band": "MODERATE", "total_percent": "100.00", "published_at": "2026-09-03T12:30:00Z", "is_active": true }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role (E10-S3 AC4) |
  | 409 | `VERSION_CONFLICT` | Concurrent publish for the same `(risk_band, version)` — the composite unique constraint rejects the second write; **no silent overwrite** (BRD §11, E10-S2 AC3) |
  | 422 | `TEMPLATE_SUM_INVALID` | Percentages sum to anything other than exactly 100 (e.g. 99 or 101). **Nothing is written** (E10-S3 AC2, E10-S2 AC1, BRD §11). `details.sum_bps` returns the actual total |
  | 422 | `VALIDATION_ERROR` | Unknown `asset_class_id`, duplicate asset class, negative percent, wrong decimal scale, or an empty `allocations` array |
- **Side effects:** inserts the new `AllocationTemplate` with `is_active = true`, flips the prior active row for that band to `is_active = false`, writes one `AuditLogEntry` (`entity_type = "AllocationTemplate"`, `action = "PUBLISH_ALLOCATION_TEMPLATE"`).
- **Notes:** the sum-to-100 rule is checked in basis points (`sum == 10000`) with no tolerance, at the repository boundary and again as an architecture test (NFR-08, E5-S1 AC1). The UI disables Publish until the running total is exactly 100 (E10-S4 AC2); this endpoint is the authoritative second gate.

### 12.6 `GET /api/admin/asset-classes`

- **Story:** E10-S4 (AC4), E10-S1 (AC4)
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** no parameters.
- **Success — 200:** `[ { "id": 1, "code": "EQ_DM", "name": "Developed-Market Equity" } ]`, ordered by `code ASC`.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
- **Side effects:** none.

### 12.7 `POST /api/admin/asset-classes`

- **Story:** E10-S3 (AC3, AC4), E10-S2 (AC5)
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `{ "code": "EQ_EM", "name": "Emerging-Market Equity" }`. `code` 1–20 chars, uppercase alphanumeric plus underscore; `name` 1–100 chars.
- **Success — 201:** `{ "id": 6, "code": "EQ_EM", "name": "Emerging-Market Equity" }`
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
  | 409 | `DUPLICATE_ASSET_CLASS_CODE` | `code` already exists (E10-S3 AC3, E10-S2 AC5) — surfaced inline by the UI (E10-S4 AC4) |
  | 422 | `VALIDATION_ERROR` | Missing/empty `code` or `name`, or `code` failing the character rule |
- **Side effects:** inserts an `AssetClass`; writes one `AuditLogEntry` (`action = "CREATE_ASSET_CLASS"`).
- **Notes:** a new asset class does not appear in any allocation until a new template version including it is published.

### 12.8 `PATCH /api/admin/asset-classes/{asset_class_id}`

- **Story:** E10-S1 (AC4)
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** path `asset_class_id` (integer). Body partial: `{ "name": "Emerging-Market Equity (ex-China)" }`. `code` and `name` are updatable; `id` is not.
- **Success — 200:** the updated asset class object.
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
  | 404 | `ASSET_CLASS_NOT_FOUND` | Unknown id |
  | 409 | `DUPLICATE_ASSET_CLASS_CODE` | New `code` collides with an existing one |
  | 422 | `VALIDATION_ERROR` | Empty body or invalid field value |
- **Side effects:** updates the row; writes one `AuditLogEntry` (`action = "UPDATE_ASSET_CLASS"`).
- **Notes:** historical `AllocationTemplate` rows reference `asset_class_id`, so renaming never rewrites a published template (E10-S1 AC4). There is no delete endpoint — an asset class referenced by history cannot be removed.

### 12.9 `GET /api/admin/rebalancing-thresholds`

- **Story:** `system-design.md` §6.1 (resolves BRD §13 open question 2)
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** no parameters.
- **Success — 200:** all versions, ordered by `version ASC`.
  ```json
  [ { "id": 1, "version": 1, "threshold_bps": 500, "threshold_percent": "5.00", "published_at": "2026-09-01T09:00:00Z", "is_active": true } ]
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
- **Side effects:** none.

### 12.10 `POST /api/admin/rebalancing-thresholds`

- **Story:** `system-design.md` §6.1; BRD §5.1 ("default 5%, versioned alongside allocation rules, editable by Admin")
- **Auth:** `admin`.
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** `{ "threshold_bps": 750 }` — integer basis points, 1–10000. Deliberately an integer, not a percent string, so the published value is exact (NFR-01). `version` is server-assigned.
- **Success — 201:**
  ```json
  { "id": 2, "version": 2, "threshold_bps": 750, "threshold_percent": "7.50", "published_at": "2026-09-03T13:00:00Z", "is_active": true }
  ```
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated |
  | 403 | `ROLE_NOT_PERMITTED` | Non-admin role |
  | 409 | `VERSION_CONFLICT` | Concurrent publish claimed the same next version |
  | 422 | `VALIDATION_ERROR` | `threshold_bps` missing, non-integer, ≤ 0, or > 10000 |
- **Side effects:** inserts the new `RebalancingThreshold` with `is_active = true`, flips the prior active row to `false`, writes one `AuditLogEntry` (`entity_type = "RebalancingThreshold"`, `action = "PUBLISH_REBALANCING_THRESHOLD"`).
- **Notes:** existing pending `RebalancingRecommendation` rows are unaffected — each embeds the `threshold_bps` and `threshold_version` it was generated under, so it stays explainable. The new threshold applies from the next advance-a-day.

---

## 13. Compliance / Audit

### 13.1 `GET /api/audit`

- **Story:** E3-S3 (AC1–AC5), E3-S4
- **Auth:** **`compliance` only.** A `customer`-, `advisor`- or `admin`-role token returns 403 (E3-S3 AC2).
- **Rate limit:** none — out of scope per BRD §5.2.
- **Request:** all query parameters optional.
  | Param | Type | Notes |
  |---|---|---|
  | `actor_id` | integer | Exact match on `AuditLogEntry.actor_id` |
  | `entity_type` | enum | Exact match — one of `RiskBandAssignment`, `AllocationRecommendation`, `RebalancingRecommendation`, `AdvisorOverride`, `ManualRecommendation`, `RiskBandRule`, `AllocationTemplate`, `AssetClass`, `RebalancingThreshold` |
  | `from` | date `YYYY-MM-DD` | Inclusive lower bound on `timestamp` |
  | `to` | date `YYYY-MM-DD` | Inclusive upper bound — the whole day is included |
  | `limit` | integer | Default 50, max 200 |
  | `offset` | integer | Default 0 |
- **Success — 200:**
  ```json
  {
    "total": 137,
    "limit": 50,
    "offset": 0,
    "entries": [
      { "id": 501, "entity_type": "RiskBandAssignment", "entity_id": "12", "actor_id": 3, "actor_role": "customer", "action": "ASSIGN_RISK_BAND", "timestamp": "2026-09-03T10:15:00Z", "details_json": { "customer_id": 3, "risk_band": "MODERATE", "rule_version": 1 } }
    ]
  }
  ```
  Ordered by `timestamp ASC` (E3-S1 AC4). `entity_type=RiskBandAssignment` returns **only** exact matches (E3-S3 AC4).
- **Errors:**
  | Status | Code | When |
  |---|---|---|
  | 401 | `TOKEN_MISSING` | Unauthenticated (E3-S3 AC5) |
  | 403 | `ROLE_NOT_PERMITTED` | customer / advisor / admin token (E3-S3 AC2) |
  | 405 | `METHOD_NOT_ALLOWED` | `POST`, `PUT`, `PATCH` or `DELETE` on `/api/audit` — **no write method is registered on this path** (E3-S3 AC3) |
  | 400 | `INVALID_QUERY_PARAMETER` | Unparseable date, `entity_type` outside the enum, `limit` > 200 |
- **Side effects:** none. This route is read-only by construction.
- **Notes:** `details_json` contains ids, enums and version numbers only (NFR-03, E3-S1 AC5). The single exception is `entity_type = "ManualRecommendation"`, whose `details_json.note` carries the advisor's free-text note — that note is the record itself (`system-design.md` §6.4) and is never written to application logs.

---

## 14. Role × Endpoint Matrix (NFR-04)

`✔` permitted · `403` authenticated but forbidden · `—` public

| Endpoint | customer | advisor | admin | compliance | anonymous |
|---|---|---|---|---|---|
| `GET /health` | — | — | — | — | ✔ |
| `POST /api/auth/login` | — | — | — | — | ✔ |
| `GET /api/auth/me` | ✔ | ✔ | ✔ | ✔ | 401 |
| `GET /api/risk-profile/questionnaire` | ✔ | 403 | 403 | 403 | 401 |
| `POST /api/risk-profile/submit` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/risk-profile/latest` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/recommendation` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/holdings` | ✔ | 403 | 403 | 403 | 401 |
| `POST /api/goals` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/goals` | ✔ | 403 | 403 | 403 | 401 |
| `PATCH /api/goals/{goal_id}` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/goals/{goal_id}/progress` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/rebalancing` | ✔ | 403 | 403 | 403 | 401 |
| `POST /api/rebalancing/{id}/accept` | ✔ | 403 | 403 | 403 | 401 |
| `POST /api/rebalancing/{id}/dismiss` | ✔ | 403 | 403 | 403 | 401 |
| `GET /api/advisor/customers` | 403 | ✔ | 403 | 403 | 401 |
| `GET /api/advisor/customers/{id}` | 403 | ✔ | 403 | 403 | 401 |
| `POST /api/advisor/customers/{id}/override` | 403 | ✔ | 403 | 403 | 401 |
| `POST /api/advisor/customers/{id}/manual-recommendation` | 403 | ✔ | 403 | 403 | 401 |
| `POST /api/admin/advance-day` | 403 | 403 | ✔ | 403 | 401 |
| `GET /api/admin/risk-band-rules` | 403 | 403 | ✔ | 403 | 401 |
| `POST /api/admin/risk-band-rules` | 403 | 403 | ✔ | 403 | 401 |
| `GET /api/admin/allocation-templates` | 403 | 403 | ✔ | 403 | 401 |
| `POST /api/admin/allocation-templates` | 403 | 403 | ✔ | 403 | 401 |
| `GET /api/admin/asset-classes` | 403 | 403 | ✔ | 403 | 401 |
| `POST /api/admin/asset-classes` | 403 | 403 | ✔ | 403 | 401 |
| `PATCH /api/admin/asset-classes/{id}` | 403 | 403 | ✔ | 403 | 401 |
| `GET /api/admin/rebalancing-thresholds` | 403 | 403 | ✔ | 403 | 401 |
| `POST /api/admin/rebalancing-thresholds` | 403 | 403 | ✔ | 403 | 401 |
| `GET /api/audit` | 403 | 403 | 403 | ✔ | 401 |

Note the deliberate asymmetries: **admin has no access to customer data endpoints** and **compliance has no access to anything but the audit log**. This is the controller-layer role separation NFR-04 requires, and it is asserted by `tests/api/test_role_matrix.py`, which drives this table row by row.

---

## 15. Edge-Case Coverage (BRD §11)

| BRD edge case | Endpoint | Status | Code |
|---|---|---|---|
| Template percentages don't sum to 100 | `POST /api/admin/allocation-templates` | 422 | `TEMPLATE_SUM_INVALID` |
| Two admins publish the same band concurrently | `POST /api/admin/allocation-templates` | 409 | `VERSION_CONFLICT` |
| Incomplete questionnaire submission | `POST /api/risk-profile/submit` | 422 | `INCOMPLETE_QUESTIONNAIRE` |
| Rebalancing for a customer with zero holdings | `POST /api/admin/advance-day` | 200 | no-op — no recommendation created, not an error |
| `kyc_verified = false` | `POST /api/admin/advance-day` | 200 | customer skipped; no recommendation created |
| Double-triggering advance-a-day on the same day | `POST /api/admin/advance-day` | 409 | `DAY_ALREADY_ADVANCED` |
| Accept/dismiss an already-resolved recommendation | `POST /api/rebalancing/{id}/accept|dismiss` | 409 | `ALREADY_RESOLVED` |
| Advisor override racing a fresh risk-band recompute | `POST /api/advisor/customers/{id}/override` | 201 | Single-transaction read-then-insert; the loser sees the winner's band as `previous_band` |
| Duplicate asset-class code | `POST /api/admin/asset-classes` | 409 | `DUPLICATE_ASSET_CLASS_CODE` |

There is no external notification channel — every "notification" is this synchronous response plus, where applicable, an `AuditLogEntry` (BRD §11, §5.2).
