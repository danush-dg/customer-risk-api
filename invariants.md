# INVARIANTS.md — Customer Risk API
*Version 2.0 · DataGrokr Engineering · 2026*

---

## How to read this document

Each invariant states a condition that must never be violated. The violation scenario describes what concretely goes wrong in terms of a real outcome — a decision made on wrong data, a credential exposed, a write executed. The testability note states exactly how you would know the invariant was violated. If you cannot answer that question, the invariant is too vague.

---

## Data Correctness

---

**INV-01 — The API response values must exactly match what the database holds for that customer.**

The `risk_tier` string and every element of the `risk_factors` list returned in the API response must be character-for-character equal to the values stored in the `customer_risk_profiles` table for that row. No transformation, normalisation, capitalisation change, or default substitution is permitted between the database row and the JSON response.

The database is the authoritative source. `init.sql` must declare a `CHECK` constraint — `CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))` — on the `customer_risk_profiles` table so that non-canonical values are rejected at insert time and can never propagate to the API. INV-01 and INV-08 are jointly enforced by this constraint.

*Violation scenario:* An operations analyst sees `MEDIUM` for a customer whose database record was updated to `HIGH`. A compliance decision is made on a stale or transformed value. The API has become a second source of truth that diverges from the database.

*Testability:* Query the database directly for a known `customer_id`. Call the API for the same ID. Compare `risk_tier` and each element of `risk_factors` character by character — they must match exactly. Confirm `init.sql` includes `CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))` on the column definition.

---

**INV-02 — Every customer present in the database must be retrievable via the API.**

For any `customer_id` that exists in `customer_risk_profiles`, an authenticated `GET /customers/{customer_id}` must return HTTP 200 with that customer's data. The API must not silently filter, exclude, or return a 404 for a customer who is in the database.

The lookup is exact-match and case-sensitive. The `customer_id` values in `init.sql` and in all test calls must be byte-identical. No normalisation occurs inside the query or anywhere in the request path.

*Violation scenario:* A customer exists in the database at tier `HIGH` but the API returns 404 for their ID. An analyst concludes the customer has no risk profile and makes a downstream decision based on the absence. The data was there; the API hid it.

*Testability:* For each `customer_id` in the seed data, call the API with that exact ID string — every call must return 200. Verify that the IDs used in test calls are byte-identical to the values stored in `init.sql`. Do not assume any normalisation occurs.

---

## Existence Mapping

---

**INV-03 — A customer ID not present in the database must return HTTP 404 with a static body, and nothing else.**

When a `customer_id` has no matching row in `customer_risk_profiles`, the API must return exactly HTTP 404. The response body must be exactly `{"detail": "Customer not found"}` — a static string literal. The response body must not contain the submitted `customer_id` value under any key. The API must not return 200 with an empty body, 200 with null fields, 500, or any other status code.

*Violation scenario:* A caller receives HTTP 200 with `risk_tier: null` for a non-existent customer. Downstream logic that checks for a truthy tier value silently treats null as a valid state. A customer with no profile is processed as if they have one.

*Testability:* Call the API with a `customer_id` known not to be in the database. Assert HTTP 404. Assert the response body is exactly `{"detail": "Customer not found"}`. Assert the submitted ID does not appear anywhere in the response body. Assert no `risk_tier` or `risk_factors` data appears.

---

**INV-04 — The 404 response for a missing customer must not reveal whether the ID format was valid or invalid.**

The detail string in a 404 response must be the static literal `"Customer not found"` — not an f-string, not a formatted message, not any expression referencing the submitted value — regardless of whether the submitted ID was plausible (`CUST-999`) or nonsensical (`; DROP TABLE`). The response must not distinguish between "ID format invalid" and "ID not found."

*Violation scenario:* An attacker probes the API with malformed IDs. A different error message for format errors vs. missing records reveals the expected ID format and confirms whether an ID exists. Information about the system's internal validation logic is exposed.

*Testability:* Call the API with a well-formed but absent ID. Call it with a malformed ID. The HTTP status code must be 404 in both cases. The response body must be exactly `{"detail": "Customer not found"}` in both cases. Code review: confirm the detail value is a string literal, not an f-string or any expression referencing the submitted value.

---

## Mutability

---

**INV-05 — No API request may cause any write, update, or delete operation on the database.**

The system is read-only. No endpoint, no request body, no query parameter, and no crafted `customer_id` value may result in an `INSERT`, `UPDATE`, `DELETE`, or DDL statement being executed against the database. This includes indirect writes through triggers or stored procedures.

*Violation scenario:* A crafted `customer_id` containing SQL syntax causes the parameterised query to be bypassed and a `DELETE` or `UPDATE` to execute. Risk profile data is modified or destroyed with no human-initiated change in the audit trail.

*Testability:* Review `db.py` — confirm every query uses psycopg2 parameterised placeholders (`%s` with a values tuple), never string formatting or concatenation. Submit at minimum these three `customer_id` values as injection attempts:

- `'; DROP TABLE customer_risk_profiles; --`
- `1 OR 1=1`
- `CUST-001'; UPDATE customer_risk_profiles SET risk_tier='LOW' WHERE '1'='1`

After each call, run `SELECT COUNT(*) FROM customer_risk_profiles` and spot-check at least one row's values across all tables in the schema — all must be unchanged. Note: parameterised queries make these tests confirmatory. The primary defence is the code review of `db.py`, not the injection tests themselves.

---

**INV-06 — The database schema must not contain any trigger or stored procedure that executes a write as a side effect of a read.**

Even if the application code is correct, a trigger on `SELECT` or a function called during a read could cause a write. The schema itself must be free of any such construct.

*Violation scenario:* A `SELECT` on `customer_risk_profiles` fires an audit trigger that writes to a log table with no size limit. The disk fills and the database crashes. Or: the trigger modifies a row, making the next read return different data than the previous one.

*Testability:* Review `db/init.sql` directly. Confirm no `CREATE TRIGGER` or `CREATE FUNCTION` statements are present. There is no runtime test for absence — this is a static review invariant.

---

## Response Shape

---

**INV-07 — The customer lookup response must always contain exactly these fields: `customer_id`, `risk_tier`, `risk_factors`.**

Every HTTP 200 response from `GET /customers/{customer_id}` must contain all three fields. No field may be absent, null, or replaced with an alternative name. No additional fields may appear. The shape must be identical regardless of which customer is queried or which tier they belong to.

The `CustomerResponse` Pydantic model in `schemas.py` must be declared with `model_config = ConfigDict(extra='forbid')`. Using `extra='ignore'` is insufficient — it silently discards new database columns rather than failing explicitly when the schema diverges from the API contract. `extra='forbid'` makes a database schema change that adds a column into an explicit, visible error.

*Violation scenario:* A `HIGH` tier customer has an empty `risk_factors` list in the database. The API omits the `risk_factors` field entirely rather than returning `[]`. A downstream tool that keys on the presence of `risk_factors` throws a `KeyError` and fails silently, treating a high-risk customer as having no factors.

*Testability:* Call the API for a customer from each tier (LOW, MEDIUM, HIGH). For each response: assert HTTP 200, assert exactly the three fields are present, assert no null values, assert `risk_factors` is always a list (including when empty). Confirm `schemas.py` declares `model_config = ConfigDict(extra='forbid')` on `CustomerResponse`.

---

**INV-08 — The `risk_tier` value must be exactly one of: `LOW`, `MEDIUM`, `HIGH` — uppercase, no variations.**

The API must never return a tier value that is not one of these three strings. Lowercase, mixed case, abbreviations, or numeric equivalents are violations.

The Pydantic schema enforces this at the serialisation boundary — but only if the route is correctly wired. The route decorator must include `response_model=CustomerResponse` explicitly, and the handler function must carry a return type annotation of `-> CustomerResponse`. Both are required for FastAPI to invoke Pydantic validation on the response. A missing `response_model` is not caught by tests that pass correct data — it only reveals itself when bad data is returned.

*Violation scenario:* The database contains `low` for a legacy record. The API returns `"risk_tier": "low"`. A downstream system doing a string comparison against `"LOW"` misclassifies the customer.

*Testability:* Confirm the route decorator is `@router.get('/customers/{customer_id}', response_model=CustomerResponse)` and the handler signature is `def get_customer(...) -> CustomerResponse:`. Query each tier from the seed data via the API and assert the exact string values `LOW`, `MEDIUM`, `HIGH`. To confirm Pydantic enforcement is active: temporarily insert a row with `risk_tier = 'low'` directly in the DB and call the endpoint — it must return 500, not `"low"`.

---

## Authentication

---

**INV-09 — Any request to `GET /customers/{customer_id}` without a valid `X-API-Key` header must return HTTP 401.**

This applies to: missing header, empty header value, wrong key value, and a valid key value submitted under a different header name. No customer data may be returned in the response body of a 401.

The wrong-header-name case requires particular attention. If `verify_api_key` is implemented as a FastAPI `Header` dependency with a required (non-optional) type, a request carrying no `X-API-Key` header will cause FastAPI to return 422 Unprocessable Entity before the dependency runs. A 422 is a violation of this invariant because it reveals to the caller that the request was structurally understood, which discloses the expected header name. The dependency must use `Header(default=None)` so that a missing header arrives as `None` and the dependency raises `HTTPException(401)` explicitly.

*Violation scenario:* The `verify_api_key` dependency is attached to the wrong route, or a route decorator ordering issue causes it to be skipped. An unauthenticated caller receives customer risk data.

*Testability:*

- Call with no `X-API-Key` header — assert 401, not 422.
- Call with an incorrect key — assert 401.
- Call with an empty string as the key — assert 401.
- Call with `Authorization: Bearer <correct-key>` and no `X-API-Key` header — assert 401, not 422.

In each case, assert no `risk_tier` or `risk_factors` data appears in the response body.

---

**INV-10 — The `/health` endpoint must not require authentication and must not return any data beyond `{"status": "ok"}`.**

`/health` is unauthenticated by design (see ARCHITECTURE.md, Decision 5). Its response must be exactly `{"status": "ok"}` — nothing more. No version numbers, no database connection state, no internal host information.

A `HealthResponse` Pydantic model must exist in `schemas.py` with `status: str` and `model_config = ConfigDict(extra='forbid')`. The `/health` route decorator must include `response_model=HealthResponse`. Without both requirements, the response shape has no enforcement and can grow silently — particularly dangerous given the endpoint is unauthenticated.

*Violation scenario (auth required):* The Docker Compose healthcheck cannot authenticate, marks the container unhealthy, and the stack fails to start.

*Violation scenario (response grows):* A developer adds `{"status": "ok", "db_host": "db:5432"}`. The internal hostname is now readable by anyone who can reach port 8000.

*Testability:* Call `/health` with no API key — assert HTTP 200. Assert the response body is exactly `{"status": "ok"}` with no additional fields. Confirm `schemas.py` declares a `HealthResponse` model with `model_config = ConfigDict(extra='forbid')` and that the route decorator includes `response_model=HealthResponse`.

---

## Credential Handling

---

**INV-11 — The API key must never appear in any HTTP response body, at any status code, under any condition.**

This includes: 401 responses where the submitted key is invalid, 422 validation errors, 500 internal errors, and any debug output. The error detail string for a 401 must be a static literal — not an f-string, not a formatted message containing the submitted value.

*Violation scenario:* `verify_api_key` raises `HTTPException(401, detail=f"Invalid key: {api_key}")`. An attacker submits a partial key and receives a 401 confirming the format of the expected key. Or: the correct key is submitted and a 500 occurs — the key appears in a traceback logged to stdout.

*Testability:* Submit a known wrong key to `GET /customers/{customer_id}`. Assert the response body does not contain the submitted key string. Submit the correct key to an endpoint that will 500 (e.g. stop the db container). Assert the response body does not contain the key. Code review `auth.py`: confirm the detail value is a string literal, not an f-string or any expression referencing the submitted value.

---

**INV-12 — The `.env` file must not exist in version control. Only `.env.example` may be committed.**

The `.env` file contains the live API key and database credentials. If committed — even once and then removed — the credentials exist in git history and are recoverable.

*Violation scenario:* `.env` is committed in the initial scaffold. The repository is shared with a team member. The API key and database password are in git history and cannot be fully removed without a history rewrite.

*Testability:*

- Run `git ls-files | grep -E '^\.env$'` — must return nothing (working tree check).
- Run `git log --all --full-history -- .env` — must return nothing (history check).

Both checks are required. A file removed from tracking via `git rm --cached` passes the first check while remaining fully recoverable from history. If the history check returns any commits, the repository must not be shared until history is rewritten. `.env.example` must be present.

---

## Error Surfaces

---

**INV-13 — A database connection failure must return HTTP 500 with a generic message. No connection string, hostname, port, username, or exception text may appear in the response body.**

When the database is unavailable, psycopg2 raises an `OperationalError` containing the connection parameters. This exception must be caught in `db.py` and replaced with a generic HTTP 500 before it reaches the response serialiser.

The `except` block must raise `HTTPException(status_code=500, detail="Internal server error")` where `"Internal server error"` is a string literal. The variable holding the caught exception must not appear anywhere in the `raise` statement — not as `str(e)`, not as `e.args[0]`, not in any f-string or formatted expression.

*Violation scenario:* The database container is restarted while the API is running. The next request causes psycopg2 to raise `connection to server at "db" (172.18.0.2), port 5432 failed`. This string reaches the caller. An attacker now knows the internal network topology.

*Testability:* Stop the `db` container with the API still running. Call `GET /customers/{customer_id}` with a valid key. Assert HTTP 500. Assert the response body is exactly `{"detail": "Internal server error"}`. Assert no hostname, port, username, or exception class name appears. Code review `db.py`: confirm the `except` block raises with a string literal and that the caught exception variable does not appear in the `raise` statement.

---

**INV-14 — A psycopg2 exception of any kind must not propagate unhandled to FastAPI's default exception handler.**

FastAPI's default handler for unhandled exceptions returns a 500 with the exception message as the detail. Any psycopg2 exception — connection failure, query error, cursor error, or type error — must be caught explicitly in `db.py` and converted to a controlled HTTP response before reaching FastAPI's handler.

Each function in `db.py` must use a two-clause try/except: `except psycopg2.Error` as the primary catch for all psycopg2 exceptions, followed by a bare `except Exception` as a fallback for any non-psycopg2 exception (such as a `TypeError` from passing wrong argument types to the cursor). Both clauses must raise `HTTPException(status_code=500, detail="Internal server error")` with no reference to the caught exception variable. No exception from `db.py` may reach FastAPI's default handler under any condition.

*Violation scenario:* A query produces a `ProgrammingError` due to a schema mismatch. FastAPI's default handler returns `{"detail": "column \"risk_tier\" of relation \"customer_risk_profiles\" does not exist"}`. The caller learns the table name, the column name, and the nature of the schema problem.

*Testability:* Code review `db.py` — confirm every function containing psycopg2 calls has both `except psycopg2.Error` and `except Exception` clauses, each raising `HTTPException(500)` with a static detail string, and that neither clause references the caught exception variable. Stop the `db` container and call the endpoint — assert HTTP 500 with exactly `{"detail": "Internal server error"}`.

---

## Operational Isolation

---

**INV-15 — The system must make no outbound network calls to any address outside the Docker Compose internal network.**

The API container must not call any external IP, hostname, or service. DNS resolution for external addresses must not occur. The only permitted network traffic is: API container → db container on the internal Docker network, and host → API container on the exposed port.

*Violation scenario:* A dependency silently phones home with telemetry or a licence check. An outbound call from an internal risk data system is a data leakage vector regardless of what is sent.

*Testability:* Review `requirements.txt` and all application modules for any `requests`, `httpx`, or socket calls. Confirm `docker-compose.yml` defines no external network. Confirm no external DNS names appear in any configuration file. This is a static review invariant.

---

## UI Fidelity

---

**INV-16 — The UI must render all API response values exactly as returned. No mapping, substitution, reformatting, or conditional display logic is permitted on any response path.**

The JavaScript in `index.html` must take values from the API JSON response and insert them into the DOM directly for all response paths — both the 200 success case and all error cases (401, 404, 500).

For the 200 path: `risk_tier` and each element of `risk_factors` must be rendered verbatim. No mapping of `"HIGH"` to `"High Risk"`, no conditional CSS classes keyed on tier value, no transformation of factor strings.

For non-200 paths: the `detail` field from the error response body must be displayed as returned — without substituting a user-friendly alternative string. The HTTP status code and the raw `detail` value must both be visible to the user.

All DOM assignments for API-sourced values must use `element.textContent`, not `element.innerHTML`. `textContent` satisfies the verbatim requirement while preventing HTML injection from database-sourced values. `innerHTML` is a violation even when the values are expected to be plain strings.

*Violation scenario (success path):* The UI maps `HIGH → "High Risk"`. The database is updated to add a fourth tier `CRITICAL`. The API returns `"CRITICAL"`. The UI has no mapping for it and displays blank output or throws a JavaScript error. Operations staff sees nothing for the highest-risk customer.

*Violation scenario (error path):* The UI displays "Access denied — check your credentials" for a 401. The raw `detail` field is obscured. An operator cannot distinguish between a wrong key and a missing key from the UI alone.

*Violation scenario (innerHTML):* A malicious value in `risk_tier` containing `<script>alert(1)</script>` is injected into the DOM via `innerHTML` and executes in the operator's browser.

*Testability:* Code review `index.html` — confirm no switch statements, object maps keyed on tier or factor values, or ternary expressions that branch on response content. Confirm every DOM assignment for API-sourced values uses `textContent`. Call the API for customers from each tier and assert the UI displays the exact strings from the JSON. Trigger a 401 and a 404 and assert the raw `detail` strings and status codes are visible.

---

## Route Completeness

---

**INV-17 — The system must expose exactly three routes. No undeclared route may exist.**

The complete set of routes in the application is: `GET /`, `GET /health`, and `GET /customers/{customer_id}`. Any request to any other path or method must return 404 (unknown path) or 405 (wrong method on a known path). No route may be added to `router.py` or `main.py` without a corresponding update to this invariant and the architecture documentation.

*Violation scenario:* A developer adds a `GET /debug` route during development and forgets to remove it before review. The route exposes internal state with no authentication because the developer assumed it was temporary. Without this invariant, there is no review checkpoint for the route set.

*Testability:* In a unit test, enumerate all routes: `[r.path for r in app.routes]`. Assert the set is exactly `{'/', '/health', '/customers/{customer_id}'}` plus any internal FastAPI framework routes (OpenAPI, redoc). Assert `POST /customers/CUST-001` returns 405. Assert `GET /admin` returns 404.

---

## Startup Validation

---

**INV-18 — The application must validate the `API_KEY` environment variable on startup and refuse to start if it is absent, empty, or shorter than 16 characters.**

A missing or empty `API_KEY` creates a condition where `verify_api_key` compares the submitted header against an empty string — and a request with an empty `X-API-Key` header passes authentication. The application must not reach a state where it accepts connections with an invalid key configuration.

On startup, before binding to any port, the application must check that `API_KEY` is present, non-empty, and at least 16 characters in length. If any of these conditions fail, the application must exit with a non-zero status code and log an explicit error message identifying the problem.

*Violation scenario:* `.env` contains `API_KEY=` (accidentally left blank). The application starts, binds to port 8000, and accepts any request with an empty `X-API-Key` header as authenticated. All customer risk data is accessible without credentials.

*Testability:* Start the container with `API_KEY=` (empty) — assert the process exits non-zero and does not bind to port 8000. Start with `API_KEY=tooshort` (fewer than 16 characters) — assert the same failure. Start with a valid key of 16+ characters — assert normal startup. Confirm the validation logic is in `main.py` and executes before `uvicorn.run()` is called.

---

## Invariant Summary

| ID | Category | One-line statement |
|---|---|---|
| INV-01 | Data correctness | Response values match the database character-for-character; DB CHECK constraint enforces canonical tier values |
| INV-02 | Data correctness | Every database customer is retrievable; lookup is exact-match and case-sensitive |
| INV-03 | Existence mapping | Missing customer returns 404 with exact static body `{"detail": "Customer not found"}` only |
| INV-04 | Existence mapping | 404 detail is the static literal "Customer not found" for all absent IDs; f-strings prohibited |
| INV-05 | Mutability | No request may cause a database write; three specified injection strings must be tested |
| INV-06 | Mutability | No trigger or procedure may write on a read; static review of init.sql |
| INV-07 | Response shape | All three fields present in every 200; `CustomerResponse` uses `extra='forbid'` |
| INV-08 | Response shape | `risk_tier` is exactly LOW, MEDIUM, or HIGH; `response_model=CustomerResponse` required on route decorator |
| INV-09 | Authentication | No customer data without a valid `X-API-Key`; wrong header name returns 401 not 422 |
| INV-10 | Authentication | `/health` is unauthenticated; `HealthResponse` model with `extra='forbid'` and `response_model=` required |
| INV-11 | Credential handling | API key never in any response body at any status code |
| INV-12 | Credential handling | `.env` never in version control; both working-tree and git history checks required |
| INV-13 | Error surfaces | DB connection failure returns `{"detail": "Internal server error"}` only; `str(e)` in detail prohibited |
| INV-14 | Error surfaces | No psycopg2 exception reaches FastAPI's default handler; dual-clause catch required in every db.py function |
| INV-15 | Operational isolation | No outbound calls outside the Docker Compose internal network |
| INV-16 | UI fidelity | UI renders all API values verbatim via `textContent` on all response paths including errors |
| INV-17 | Route completeness | System exposes exactly `GET /`, `GET /health`, `GET /customers/{customer_id}` and nothing else |
| INV-18 | Startup validation | Application refuses to start if `API_KEY` is absent, empty, or fewer than 16 characters |

---

*Customer Risk API · INVARIANTS.md v2.0 · DataGrokr Engineering · 2026*