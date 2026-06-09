# CLAUDE.md
**Customer Risk API** · Version 1.0 · DataGrokr Engineering · 2026
*Frozen execution contract — do not modify this file*

---

## 1. System Intent

The Customer Risk API provides authenticated, read-only HTTP access to pre-assessed customer risk tier data stored in Postgres. It replaces direct database access with a single defined interface so operations staff can query risk status without SQL. The system surfaces data — it does not compute, transform, or assess risk.

---

## 2. Hard Invariants

These conditions must never be violated. If a task conflicts with any invariant, stop and flag the conflict — do not resolve it silently.

- **INV-01** The API reads from the database on every request. Values returned must match the database row exactly. No caching.
- **INV-02** Any `customer_id` value returns exactly 200 (found) or 404 (not found). No other status code is valid for a request that reaches lookup logic with a valid key.
- **INV-03** No write operation — INSERT, UPDATE, DELETE, DDL — is reachable through any endpoint under any input.
- **INV-04** The SQL query is a static string. `customer_id` is passed as a psycopg2 query parameter (`%s`). No string formatting or concatenation.
- **INV-05** Every 200 response contains exactly three fields: `customer_id` (string), `risk_tier` (string), `risk_factors` (array). No extras, no omissions.
- **INV-06** `risk_tier` is always one of `LOW`, `MEDIUM`, `HIGH` — uppercase, passed through from the database unchanged.
- **INV-07** `GET /customers/{customer_id}` requires a valid `X-API-Key` header. Authentication is checked before any database interaction. `GET /health` and `GET /` are unauthenticated. No other routes exist.
- **INV-08** The API key never appears in any HTTP response body, header, or log output. The 401 detail string is a static literal.
- **INV-09** No internal detail appears in any response: no psycopg2 exceptions, no stack traces, no table or column names, no connection strings. Only pre-defined static literals are permitted in error response bodies: `"Unauthorized"`, `"Customer not found"`, `"Internal server error"`.
- **INV-10** The system makes no network calls outside the Docker Compose stack. No external DNS, HTTP, logging, or telemetry.
- **INV-11** The UI renders API response values without transformation. No remapping of tier strings, no reordering or filtering of factors, no display labels that differ from API values.
- **INV-12** The 401 response body is a single static literal regardless of whether the key was missing, empty, or incorrect.
- **INV-13** `GET /health` returns only `{"status": "ok"}`. No customer data, no row counts, no additional fields.

---

## 3. Scope Boundary

**Claude Code is permitted to build:**
- `db/init.sql` — schema and seed data only
- `docker-compose.yml` and `.env.example`
- `api/requirements.txt` and `api/Dockerfile`
- `api/main.py` — FastAPI application with exactly three routes: `GET /health`, `GET /`, `GET /customers/{customer_id}`
- `api/test_errors.py`, `api/test_injection.py`, `api/test_invariants.py`
- `README.md`

**Claude Code must never:**
- Modify `CLAUDE.md`
- Add routes, endpoints, or middleware not listed in the execution plan
- Add dependencies not in the fixed stack
- Write any endpoint that accepts POST, PUT, PATCH, or DELETE
- Add connection pooling, caching, or ORM
- Make external network calls from application code
- Hardcode credentials

---

## 4. Fixed Stack

These choices are locked. No alternatives, no additions.

| Component | Technology |
|---|---|
| Orchestration | Docker Compose |
| Database | Postgres 15 |
| API runtime | FastAPI · Python 3.11 |
| Database driver | psycopg2-binary — no ORM, no connection pool |
| UI | Inline HTML + vanilla JavaScript — no framework, no CDN |

---

*Commit message when frozen: `chore: add CLAUDE.md v1.0 — execution contract frozen`*
*DataGrokr Engineering · PBVI Practitioner Series · 2026*