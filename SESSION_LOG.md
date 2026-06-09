# SESSION_LOG.md
**Customer Risk API** · DataGrokr Engineering · 2026

---

## Session 1 — Project Scaffold and Database
**Branch:** `session/s01_scaffold`
**Date:** 2026-06-09
**Status:** COMPLETE

### T1.1 — Create project directory structure
- Created 7 scaffold files with placeholder comments
- Verified: `find customer-risk-api -type f | sort` matched expected output exactly
- Commit: `[S1.T1] add: project directory structure — verification: PASS`

### T1.2 — Write database schema and seed data
- Wrote `db/init.sql` with `CREATE TABLE IF NOT EXISTS customer_risk_profiles`
- Columns: `customer_id VARCHAR PK`, `risk_tier VARCHAR NOT NULL`, `risk_factors TEXT[] NOT NULL`
- CHECK constraint: `risk_tier IN ('LOW', 'MEDIUM', 'HIGH')`
- 9 INSERT rows — 3 per tier (CUST-001 through CUST-009)
- No UPDATE, DELETE, triggers, or functions
- Invariants touched: INV-01, INV-03, INV-05, INV-06
- Commit: `[S1.T2] add: database schema and seed data — verification: PASS — invariants: INV-01, INV-03, INV-05, INV-06`

### T1.3 — Write docker-compose.yml and .env.example
- `db` service: `postgres:15`, mounts `init.sql`, `pg_isready` healthcheck (interval 5s, retries 5)
- `api` service: builds `./api`, port `8000:8000`, `depends_on db` with `condition: service_healthy`
- No external network definitions
- `.env.example` with exactly 6 keys; `POSTGRES_HOST=db`
- Invariants touched: INV-02, INV-07, INV-10
- Commit: `[S1.T3] add: docker-compose and env example — verification: PASS — invariants: INV-02, INV-07, INV-10`

### Integration Check
- `docker compose up db -d` — container started, image pulled
- Queried `customer_risk_profiles` — 9 rows returned, all three tiers present, no errors
- Result: PASS

---

## Session 2 — FastAPI Application Core
**Branch:** `session/s02_api`
**Date:** 2026-06-09
**Status:** COMPLETE

### T2.1 — Write requirements.txt and Dockerfile
- `requirements.txt`: `fastapi`, `uvicorn`, `psycopg2-binary` — no version pins, no extras
- `Dockerfile`: `FROM python:3.11-slim`, WORKDIR `/app`, copies and installs requirements, exposes 8000, CMD uvicorn
- Build verified: `docker compose build api` completed with no errors
- Commit: `[S2.T1] add: requirements.txt and Dockerfile — verification: PASS`

### T2.2 — Write the FastAPI application skeleton
- `main.py` with exactly 3 routes: `GET /health`, `GET /`, `GET /customers/{customer_id}`
- `/health` returns `{"status": "ok"}` — no extra fields (INV-13)
- `/` returns `HTMLResponse("UI coming soon")`
- `/customers/{customer_id}` returns `{"message": "placeholder"}` — no auth yet
- Verified: health shape assert PASS inside container
- Invariants touched: INV-13
- Commit: `[S2.T2] add: FastAPI application skeleton — verification: PASS — invariants: INV-13`

### T2.3 — Write the database connection function
- `get_db_connection()` reads 5 env vars, calls `psycopg2.connect()` directly
- On failure: catches all exceptions, raises `HTTPException(500, "Internal server error")` static literal
- Success case: PASS — connection returned when DB is up
- Failure case: PASS — correct HTTPException raised when DB is stopped
- Invariants touched: INV-09
- Commit: `[S2.T3] add: database connection function — verification: PASS — invariants: INV-09`

### T2.4 — Write the API key authentication dependency
- `async def verify_api_key(api_key: str = Header(None, alias="X-API-Key"))`
- Reads `API_KEY` from env; uses `==` comparison only; `not api_key` guard covers None and empty string
- All 7 test cases PASS: correct key, wrong key, None, empty string, prefix, trailing whitespace, identical 401 detail
- Not wired to any route (T3.1 does that)
- Invariants touched: INV-07, INV-08, INV-09, INV-12
- Commit: `[S2.T4] add: api key auth dependency — verification: PASS — invariants: INV-07, INV-08, INV-09, INV-12`

### Integration Check
- `GET /health` → `{"status":"ok"}` — PASS
- `GET /customers/CUST-001` (no key) → `{"message":"placeholder"}`, no 500 — PASS
- `GET /customers/CUST-001` (wrong key) → `{"message":"placeholder"}`, no 500 — PASS
- Note: auth placeholder responses expected — `verify_api_key` not yet wired (T3.1)
- Result: PASS

---

## Session 3 — Customer Lookup Endpoint
**Branch:** `session/s03_lookup`
**Date:** 2026-06-09
**Status:** COMPLETE

### T3.1 — Wire auth dependency and implement customer lookup
- Added `Depends(verify_api_key)` to `GET /customers/{customer_id}` route
- Parameterised SELECT query: static string with single `%s`, `customer_id` passed as tuple
- Found row → returns `{"customer_id", "risk_tier", "risk_factors"}` — exactly three keys
- No row → `HTTPException(404, "Customer not found")`
- `conn.close()` in `finally` block regardless of outcome
- Removed placeholder return
- Invariants touched: INV-01, INV-02, INV-04, INV-05, INV-06, INV-07
- Commit: `34929c2` — `[S3.T1] add: customer lookup endpoint — verification: PASS — invariants: INV-01, INV-02, INV-04, INV-05, INV-06, INV-07`

### T3.2 — Verify response values match the database directly
- Verification-only, no code changes
- Queried DB directly for CUST-001 (LOW), CUST-004 (MEDIUM), CUST-007 (HIGH)
- API responses match DB rows exactly for all three fields across all three tiers
- Invariants touched: INV-01
- Commit: `efa3b5c` — `[S3.T2] verify: data correctness against database — verification: PASS — invariants: INV-01`

### T3.3 — Verify database error handling
- Verification-only, no code changes
- Stopped `db` container, triggered authenticated request — returned `{"detail":"Internal server error"}` with `Content-Type: application/json`
- No psycopg2 exception text, no table names, no connection details in response body
- Normal operation resumed after `docker compose start db && sleep 8`
- Invariants touched: INV-09
- Commit: `0fd0fd0` — `[S3.T3] verify: database error handling — verification: PASS — invariants: INV-09`

### Integration Check
- CUST-001 (LOW), CUST-004 (MEDIUM), CUST-007 (HIGH) — correct data, exactly three fields each
- CUST-999 → `{"detail":"Customer not found"}`
- No key → `{"detail":"Unauthorized"}`
- Wrong key → `{"detail":"Unauthorized"}` — identical to no-key response
- `/health` → `{"status":"ok"}` — no extra fields
- Result: PASS

### Session Completion
- All three tasks complete, all invariants verified
- No code changes remain open — T3.2 and T3.3 were verification-only
- Branch `session/s03_lookup` ready to merge
- Next: Session 4 — Browser UI and error state tests (`session/s04_ui`)

---

## Session 4 — Browser UI and Error State Tests
**Branch:** `session/s04_ui`
**Date:** 2026-06-09
**Status:** COMPLETE

### T4.1 — Implement the browser UI
- Replaced `HTMLResponse("UI coming soon")` with full inline HTML page in `_HTML` module-level constant
- Two inputs: API Key (password type) and Customer ID (text)
- Submit button + Enter-key listener; result `<div id="result">`
- `fetch('/customers/' + encodeURIComponent(id), { headers: { 'X-API-Key': key } })` — relative path
- On 200: renders `customer_id`, `risk_tier`, `risk_factors` directly from `data.*` — no transformation
- On error: renders `data.detail` directly — covers 401, 404, 500
- No external scripts, no CDN, no framework; all HTML/CSS/JS inline in `main.py`
- Invariants touched: INV-11
- Commit: `138e641` — `[S4.T1] add: browser UI — verification: PASS — invariants: INV-11`

### T4.2 — Write automated error state tests
- Created `api/test_errors.py` using `unittest` + `requests`
- Reads `API_KEY` and `BASE_URL` from env; `BASE_URL` defaults to `http://localhost:8000`
- 5 test cases: no key → 401, wrong key → 401, empty key → 401, CUST-999 → 404, no-key/wrong-key bodies identical
- No DB reads; self-contained on env vars
- `pytest` and `requests` installed on host (`pip install pytest requests`)
- Invariants touched: INV-02, INV-07, INV-08, INV-12
- Commit: `6d7b1a3` — `[S4.T2] add: error state tests — verification: PASS — invariants: INV-02, INV-07, INV-08, INV-12`

### Integration Check
- Automated: `python -m pytest api/test_errors.py -v` — 5 collected, 5 passed
- Manual UI: `http://localhost:8000` — CUST-001/004/007 values match API responses; CUST-999 displays `Customer not found`
- Result: PASS

### Session Completion
- All two tasks complete, all invariants verified
- `test_errors.py` is the first automated test artifact — runs from host against live container
- Branch `session/s04_ui` ready to merge
- Next: Session 5 — Hardening, injection tests, full invariant run (`session/s05_harden`)

---

## Session 5 — Hardening, Injection Tests, Full Invariant Run
**Branch:** `session/s05_harden`
**Date:** 2026-06-09
**Status:** COMPLETE

### T5.1 — Write SQL injection tests
- Created `api/test_injection.py` using `unittest` + `requests`
- Reads `API_KEY`, `BASE_URL`, `POSTGRES_USER`, `POSTGRES_DB` from environment variables
- 5 SQL injection payloads: DROP TABLE, OR-true bypass, UNION SELECT, stacked query, long keyword string
- 6 test cases: 5 per-payload status checks + row count unchanged after all requests
- All payloads correctly return 404 (not 200 or 500); parameterised query blocks all injection attempts
- Invariants touched: INV-03, INV-04
- Status: COMPLETE

### T5.2 — Write the full invariant verification script
- Created `api/test_invariants.py` using `unittest` + `requests`
- Reads `API_KEY`, `BASE_URL`, `POSTGRES_USER`, `POSTGRES_DB` from environment variables
- 13 test classes covering INV-01 through INV-13 (INV-10 and INV-11 manual)
- INV-01: Direct DB comparison via `row_to_json` psql query for CUST-001, CUST-004, CUST-007
- INV-02: Existing ID → 200; CUST-999 → 404 with static literal
- INV-03: Row count recorded before requests, asserted exact match after
- INV-04: All 5 injection payloads return not-500 and not-200
- INV-05: Every 200 response has exactly three keys with correct types (str, str, list)
- INV-06: risk_tier in every 200 response is one of {LOW, MEDIUM, HIGH}
- INV-07: No key → 401; row count unchanged after unauthenticated request (proxy check)
- INV-08: Submitted key value absent from 401 response body
- INV-09: setUpClass stops DB; confirms 500 static literal and no internal detail; tearDownClass restarts DB and sleeps 10s
- INV-12: No-key and wrong-key response bodies are identical
- INV-13: /health returns exactly one key "status" with value "ok"
- Invariants touched: INV-01 through INV-13 (INV-10 and INV-11 manual)
- Status: COMPLETE

### T5.3 — Write README.md
- Wrote `customer-risk-api/README.md` with six required sections
- Sections: What it is, Prerequisites, Setup, Usage, Teardown, Stack
- Curl examples use `$API_KEY` — no hardcoded values
- `docker compose down -v` documented with explicit warning about omitting `-v`
- No references to PBVI, sessions, invariants, or internal planning artifacts
- Invariants touched: None directly
- Status: COMPLETE

### Integration Check (Final Gate)
- Full teardown: `docker compose down -v` — both containers removed, volume purged
- Cold start: `docker compose up -d` — db healthy, api up, both containers clean
- Full automated run: `python -m pytest api/test_invariants.py api/test_errors.py api/test_injection.py -v`
- Result: **34 collected, 34 passed** in 23.84s — zero 500s
- INV-10 manual: no `external:` in docker-compose.yml; no outbound imports in main.py — PASS
- INV-11 manual: `data.customer_id`, `data.risk_tier`, `data.risk_factors` written directly to DOM, no switch/remap — PASS
- All results recorded in VERIFICATION_RECORD.md
- Status: COMPLETE
