# INVARIANTS.MD
**Customer Risk API** · Version 1.0 · DataGrokr Engineering · 2026

---

## INV-01 — Data Correctness

The risk tier and factor list returned for a given `customer_id` must match the values stored in that customer's row in `customer_risk_profiles`. No transformation, no defaulting, no inference. The API reads from the database on every request. No caching layer is permitted between the API and the database.

**If violated:** an operations staff member makes a decision — escalation, clearance, flagging — based on a risk tier that does not reflect the assessed value. The API becomes a source of false data, not a window onto the database.

---

## INV-02 — Existence Mapping

For any value of `customer_id`, the only valid outcomes are 200 (found) or 404 (not found). No other status code is valid for a request that reaches the lookup logic with a valid API key. A missing customer must never return 200 with empty data, null fields, or a default tier.

**If violated:** a non-existent customer ID returns a response that looks valid. A downstream tool treats the empty or default response as authoritative. A real customer is confused with a missing one, or a missing one is treated as low-risk by default.

---

## INV-03 — No Write Operations

The API executes no write operations against the database. No `INSERT`, `UPDATE`, `DELETE`, or DDL statement is reachable through any API endpoint under any input. The database state after any sequence of API calls must be identical to its state before.

**If violated:** the pre-populated risk data — the authoritative ground truth the system is built to surface — can be altered through the API. The seed data is no longer reliable as a verification baseline. A crafted input could corrupt or destroy records.

---

## INV-04 — Parameterised Queries

The entire query is a static string with a single `%s` placeholder. The `customer_id` path parameter is passed to psycopg2 as a query parameter. No part of the query — table name, column name, or clause — is constructed from user input. No string formatting or concatenation is used.

**If violated:** a crafted `customer_id` value executes arbitrary SQL. A SQL injection string becomes a write vector. `'; DROP TABLE customer_risk_profiles; --` is the obvious case, but data exfiltration is equally possible.

---

## INV-05 — Response Shape

Every 200 response contains exactly three fields: `customer_id` (string), `risk_tier` (string), and `risk_factors` (array). The shape is consistent regardless of tier value or factor list length. No additional fields. No missing fields. No variation in key names or value types.

**If violated:** a downstream tool built against the contract breaks on an unexpected shape. A missing field causes a null reference. A wrong type on `risk_factors` breaks any tool that iterates the list. An extra field leaks internal data.

---

## INV-06 — Risk Tier Values

`risk_tier` is always one of three uppercase literal values: `LOW`, `MEDIUM`, or `HIGH`. The value is passed through from the database without transformation. No case variation is permitted. The API must not introduce a fourth value through defaulting or error handling.

**If violated:** a downstream tool with a three-value enum breaks on an unrecognised tier. A decision workflow that branches on tier value reaches an undefined state.

---

## INV-07 — Authentication Gate

`GET /customers/{customer_id}` requires a valid API key in the `X-API-Key` header. Requests without a valid key return 401 before any database interaction occurs — no connection is opened, no query is executed, no customer data is retrieved. `GET /health` and `GET /` are intentionally unauthenticated. No other routes exist.

**If violated:** any caller can retrieve customer risk data without credentials. The access control boundary the system was built to enforce does not exist.

**Verification note:** the "before DB interaction" clause must be confirmed by code review of `verify_api_key` and the route definition — it is not observable from the HTTP response alone.

---

## INV-08 — API Key Never Exposed

The API key never appears in any HTTP response body, header, or log output. The 401 detail string is a static literal. It does not echo the submitted key, does not confirm or deny what a valid key looks like, and does not vary based on the submitted value.

**If violated:** a caller who submits a wrong key receives their own key back in the error response, or receives confirmation that a guessed key is close. The authentication boundary is undermined by the error surface.

**Verification note:** the log output clause requires manual inspection or a log-scraping check in addition to the HTTP response test.

---

## INV-09 — No Internal Detail in Responses

No internal implementation detail appears in any HTTP response. This covers: psycopg2 exception messages, stack traces, table names, column names, connection strings, environment variable names, and file paths. The only permitted error response bodies are pre-defined static strings. No part of the response body is derived from exception messages, exception types, or stack traces. Permitted error literals are defined in EXECUTION_PLAN.md.

**If violated:** a caller who triggers a database error receives a traceback that reveals the schema, the connection parameters, or the technology stack. This information directly enables further attacks.

---

## INV-10 — Operational Isolation

The system makes no network calls to any address outside the Docker Compose stack. The API container communicates only with the `db` container on the internal Compose network. No DNS lookups, no HTTP calls, no external logging, no telemetry.

**If violated:** customer risk data — or metadata about queries — is transmitted to an external endpoint. The isolation guarantee is also the basis for the no-external-network constraint in `docker-compose.yml`.

**Verification note:** confirmed by two checks — code review of `main.py` for absence of outbound calls, and absence of external network definitions in `docker-compose.yml`.

---

## INV-11 — UI Fidelity

The UI renders the API response without transformation. The values displayed in the browser for `customer_id`, `risk_tier`, and `risk_factors` are the values returned by the API. The JavaScript does not remap tier strings, does not reorder or filter factors, does not apply display labels that differ from the API values, and does not add or remove content.

**If violated:** an operations staff member sees a tier label in the UI that does not match what the API returned. A factor is hidden or a label shown that was never in the data. The UI becomes a source of misrepresentation, not a display surface.

**Verification note:** requires a two-step check — fetch the API response directly, then compare field values to what the UI renders in the DOM for the same `customer_id`. Empty array rendering behaviour is pending resolution of OQ-01.

---

## INV-12 — 401 Response Is a Static Literal

The 401 response body is a single static literal regardless of whether the key was missing, empty, or incorrect. The response does not vary based on the nature of the authentication failure.

**If violated:** varying 401 messages reveal information about the authentication mechanism — confirming whether a key was present but wrong, or absent entirely. This narrows the attack surface for a caller probing the auth boundary.

---

## INV-13 — Health Endpoint Returns No Data

The `/health` endpoint returns only a static status indicator. It contains no customer data, no database row counts, no schema information, and no internal system detail.

**If violated:** the unauthenticated `/health` endpoint becomes an information leak. Any caller — without a key — can retrieve database state or schema detail through a route that is explicitly designed to be open.

---

## Summary

| ID | Category | Condition |
|---|---|---|
| INV-01 | Data correctness | API reads from DB on every request; values match database row exactly; no caching |
| INV-02 | Existence mapping | Any `customer_id` value → 200 (found) or 404 (not found) only |
| INV-03 | Mutability | No write operations reachable through any endpoint |
| INV-04 | Mutability | Entire query is static; `customer_id` value passed as parameter only |
| INV-05 | Response shape | Every 200 has exactly `customer_id` (string), `risk_tier` (string), `risk_factors` (array) |
| INV-06 | Response shape | `risk_tier` is always uppercase `LOW`, `MEDIUM`, or `HIGH` |
| INV-07 | Authentication | Customer endpoint requires valid key; 401 before any DB access; `/health` and `/` unauthenticated |
| INV-08 | Credential handling | API key never appears in any response or log |
| INV-09 | Error surfaces | Only pre-defined static strings permitted in error responses |
| INV-10 | Operational isolation | No network calls outside the Compose stack; verified by code review and compose config |
| INV-11 | UI fidelity | UI renders API values without transformation; empty array behaviour pending OQ-01 |
| INV-12 | Authentication | 401 body is a single static literal regardless of failure reason |
| INV-13 | Error surfaces | `/health` returns only a static status indicator; no data or schema detail |

---

*DataGrokr Engineering · PBVI Practitioner Series · 2026*
