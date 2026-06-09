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
**Status:** IN PROGRESS

### T4.1 — Implement the browser UI
- Status: PENDING

### T4.2 — Write automated error state tests
- Status: PENDING

### Integration Check
- Status: PENDING
