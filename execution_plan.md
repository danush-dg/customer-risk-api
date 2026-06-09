# EXECUTION_PLAN.MD
**Customer Risk API** · Version 1.0 · DataGrokr Engineering · 2026

---

## Session Map

| Session | Goal | Tasks |
|---|---|---|
| S1 | Project scaffold and database | T1.1 · T1.2 · T1.3 |
| S2 | FastAPI application core | T2.1 · T2.2 · T2.3 · T2.4 |
| S3 | Customer lookup endpoint | T3.1 · T3.2 · T3.3 |
| S4 | Browser UI and error state tests | T4.1 · T4.2 |
| S5 | Hardening, injection tests, full invariant run | T5.1 · T5.2 · T5.3 |

---

## Permitted Error Literals

These are the only strings permitted in error response bodies. No other wording is valid.

| Scenario | Literal |
|---|---|
| Unauthenticated request | `Unauthorized` |
| Customer not found | `Customer not found` |
| Internal server error | `Internal server error` |

---

## Session 1 — Project Scaffold and Database

**Goal:** Postgres running with correct schema and seed data. No application code.
**Branch:** `session/s01_scaffold`

By the end of this session you can connect directly to the database and query customer records. The API does not exist yet.

---

### Task 1.1 — Create the project directory structure

**Claude Code prompt:**
```
Create the following directory structure for the Customer Risk API project.
All files should be empty or contain a single placeholder comment.

customer-risk-api/
  db/
    init.sql
  api/
    main.py
    requirements.txt
    Dockerfile
  .env.example
  docker-compose.yml
  README.md

Do not write any content into these files. Scaffold only.
```

**Test cases:**
- All 7 paths exist
- All files are empty or contain only a placeholder comment
- No additional files or directories are present

**Verification command:**
```bash
find customer-risk-api -type f | sort
```

**Expected output:**
```
customer-risk-api/.env.example
customer-risk-api/README.md
customer-risk-api/api/Dockerfile
customer-risk-api/api/main.py
customer-risk-api/api/requirements.txt
customer-risk-api/db/init.sql
customer-risk-api/docker-compose.yml
```

**Invariants touched:** None. Structural scaffolding only.

**Commit message:** `[S1.T1] add: project directory structure — verification: PASS`

---

### Task 1.2 — Write the database schema and seed data

**Claude Code prompt:**
```
Write db/init.sql for the Customer Risk API.

Requirements:
- CREATE TABLE IF NOT EXISTS customer_risk_profiles with columns:
    customer_id VARCHAR PRIMARY KEY
    risk_tier VARCHAR NOT NULL
    risk_factors TEXT[] NOT NULL
    CHECK constraint limiting risk_tier to 'LOW', 'MEDIUM', 'HIGH'
- INSERT at least 9 customer records: minimum 3 per tier
- customer_id format: CUST-001, CUST-002, etc.
- risk_factors is an array of plain strings describing what drove the assessment
- No UPDATE, DELETE, trigger, or function definitions
- No seed data that could be confused with real customer data
```

**Test cases:**
- `CREATE TABLE IF NOT EXISTS` is present
- CHECK constraint on `risk_tier` is present limiting values to LOW, MEDIUM, HIGH
- At least 9 INSERT rows present
- At least 3 rows per tier
- No UPDATE, DELETE, trigger, or function definitions anywhere in the file
- `risk_factors` column type is `TEXT[]` — not VARCHAR or TEXT
- `risk_factors` is seeded as an array literal, not a plain string

**Verification commands:**
```bash
# Confirm tier distribution
docker compose exec db psql -U riskuser -d riskdb \
  -c "SELECT risk_tier, COUNT(*) FROM customer_risk_profiles GROUP BY risk_tier ORDER BY risk_tier;"

# Confirm column types — risk_factors must show text[]
docker compose exec db psql -U riskuser -d riskdb \
  -c "\d customer_risk_profiles"
```

**Expected output (tier count):**
```
 risk_tier | count
-----------+-------
 HIGH      |     3
 LOW       |     3
 MEDIUM    |     3
(3 rows)
```

**Expected output (column types):** `risk_factors` column shows type `text[]`.

**Invariants touched:**
- INV-01 — seed data is the ground truth all API responses are verified against
- INV-03 — schema must contain no write triggers or functions reachable at runtime
- INV-05 — `risk_factors` column type TEXT[] is the foundation of the array contract
- INV-06 — CHECK constraint enforces the three permitted tier values at the data layer

**Code review required:**
- Confirm no UPDATE, DELETE, or trigger definitions
- Confirm CHECK constraint is present and correct
- Confirm `risk_factors` column is `TEXT[]` not `VARCHAR`

**Commit message:** `[S1.T2] add: database schema and seed data — verification: PASS — invariants: INV-01, INV-03, INV-05, INV-06`

---

### Task 1.3 — Write docker-compose.yml and .env.example

**Claude Code prompt:**
```
Write docker-compose.yml and .env.example for the Customer Risk API.

docker-compose.yml requirements:
- Two services: db and api
- db service: postgres:15, mounts db/init.sql to /docker-entrypoint-initdb.d/init.sql
- db healthcheck using pg_isready, interval 5s, retries 5
- api service: builds from ./api, depends_on db with condition: service_healthy
- api service: port 8000:8000, reads from .env file
- No external network definitions — internal Compose network only
- No volumes defined beyond the implicit db data volume

.env.example requirements — exactly these six keys, no others:
  POSTGRES_USER=
  POSTGRES_PASSWORD=
  POSTGRES_DB=
  POSTGRES_HOST=db
  POSTGRES_PORT=5432
  API_KEY=
```

**Test cases:**
- `docker compose config --quiet` exits with code 0
- `db` service healthcheck command uses `pg_isready` — not a TCP check or sleep
- `api` service has `depends_on` with `condition: service_healthy`
- No external network definitions present in the file
- All six `.env.example` keys are present
- `POSTGRES_HOST` is set to `db` (the Compose service name, not localhost)

**Verification commands:**
```bash
# Confirm config is valid
cd customer-risk-api && docker compose config --quiet && echo "Config valid"

# Confirm healthcheck uses pg_isready
docker compose config | grep -A5 "healthcheck"
```

**Expected output:**
```
Config valid
```
Healthcheck output must show `pg_isready` — not a TCP check or arbitrary sleep.

**Invariants touched:**
- INV-02 — healthcheck dependency ensures API only starts when DB is ready, preventing connection errors that would produce incorrect status codes
- INV-07 — healthcheck ensures API does not start before DB is ready, preventing raw connection errors reaching the caller
- INV-10 — no external network definitions confirms operational isolation at the infrastructure level

**Code review required:**
- Confirm no `networks:` block with `external: true`
- Confirm healthcheck command is `pg_isready`, not a TCP or sleep-based check
- Confirm healthcheck interval ≤ 10s and retries ≥ 3
- Confirm `POSTGRES_HOST=db` in .env.example

**Commit message:** `[S1.T3] add: docker-compose and env example — verification: PASS — invariants: INV-02, INV-07, INV-10`

---

### Session 1 Integration Check

```bash
cd customer-risk-api
cp .env.example .env
# Edit .env — set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, API_KEY
docker compose up db -d
sleep 8
docker compose exec db psql -U riskuser -d riskdb \
  -c "SELECT customer_id, risk_tier FROM customer_risk_profiles ORDER BY risk_tier, customer_id;"
```

**Expected:** 9+ rows returned, all three tiers present, no errors.

---

## Session 2 — FastAPI Application Core

**Goal:** FastAPI container with database connection function and API key authentication dependency. No business logic yet.
**Branch:** `session/s02_api`

By the end of this session the API container starts, connects to Postgres, and rejects unauthenticated requests. The customer endpoint returns a placeholder response for authenticated requests.

---

### Task 2.1 — Write requirements.txt and Dockerfile

**Claude Code prompt:**
```
Write api/requirements.txt and api/Dockerfile for the Customer Risk API.

requirements.txt — exactly these packages, no version pins, no additional dependencies:
  fastapi
  uvicorn
  psycopg2-binary

Dockerfile requirements:
- Base image: python:3.11-slim
- Working directory: /app
- Copy requirements.txt and install dependencies
- Copy application source
- Expose port 8000
- CMD to run uvicorn on host 0.0.0.0 port 8000 with main:app
```

**Test cases:**
- `docker compose build api` completes with no errors
- Only `fastapi`, `uvicorn`, `psycopg2-binary` in requirements.txt — no additional packages, no version pins
- Dockerfile base image is exactly `python:3.11-slim` — not 3.12, not latest

**Verification commands:**
```bash
# Confirm build succeeds
cd customer-risk-api && docker compose build api 2>&1 | tail -5

# Confirm base image
grep "FROM" customer-risk-api/api/Dockerfile
```

**Expected:** Build succeeds. `FROM python:3.11-slim` in Dockerfile.

**Invariants touched:** None directly.

**Commit message:** `[S2.T1] add: requirements.txt and Dockerfile — verification: PASS`

---

### Task 2.2 — Write the FastAPI application skeleton

**Claude Code prompt:**
```
Write api/main.py as a FastAPI application skeleton for the Customer Risk API.

Requirements:
- Import FastAPI, HTMLResponse, JSONResponse from fastapi
- Create a FastAPI app instance
- Define exactly three routes:
    GET /health  — returns {"status": "ok"} and nothing else
    GET /        — returns HTMLResponse with a placeholder string "UI coming soon"
    GET /customers/{customer_id}  — returns {"message": "placeholder"} with no auth yet
- No business logic, no database calls, no auth in this task
- No additional imports, middleware, or background tasks
```

**Test cases:**
- `GET /health` returns 200 with body exactly `{"status": "ok"}` — no additional fields
- `GET /` returns 200 with HTML content
- `GET /customers/any-id` returns 200 with placeholder response
- Exactly three routes defined — no others

**Verification commands:**
```bash
docker compose up -d && sleep 5

# Confirm health returns exactly the right shape
curl -s http://localhost:8000/health | python3 -c \
  "import sys, json; d=json.load(sys.stdin); assert list(d.keys())==['status'], f'Extra fields: {d}'; print('PASS')"
```

**Expected output:** `PASS`

**Invariants touched:**
- INV-13 — `/health` must return only a static status indicator; no extra fields

**Code review required:**
- Confirm exactly three routes: `/health`, `/`, `/customers/{customer_id}`
- Confirm no middleware, no background tasks, no additional imports

**Commit message:** `[S2.T2] add: FastAPI application skeleton — verification: PASS — invariants: INV-13`

---

### Task 2.3 — Write the database connection function

**Claude Code prompt:**
```
Add a get_db_connection function to api/main.py.

Requirements:
- Reads all connection parameters from environment variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- Uses psycopg2.connect() directly — no connection pool, no ORM
- If the connection succeeds, returns the connection object
- If psycopg2 raises any exception, catches it and raises an HTTPException
  with status_code=500 and detail="Internal server error"
- The detail string is a static literal — not an f-string, not derived from the exception
- The psycopg2 exception message must not appear anywhere in the HTTPException detail
- Do not call get_db_connection from any route yet
```

**Test cases:**
- Function connects successfully when DB is running
- Function raises HTTPException 500 when DB is unavailable
- HTTPException detail is exactly the string `"Internal server error"` — no variation
- psycopg2 exception message does not appear in the 500 response body
- No hardcoded credentials anywhere in the function

**Verification commands:**
```bash
# Success case
docker compose exec api python -c \
  "import main; conn = main.get_db_connection(); print('PASS' if conn else 'FAIL')"

# Failure case — confirm exact literal and no internal detail
docker compose stop db
docker compose exec api python -c "
import main
from fastapi import HTTPException
try:
    main.get_db_connection()
    print('FAIL: no exception raised')
except HTTPException as e:
    print('PASS' if e.detail == 'Internal server error' else f'FAIL: wrong detail: {e.detail}')
except Exception as e:
    print(f'FAIL: wrong exception type: {e}')
"
docker compose start db && sleep 8
```

**Expected output:**
```
PASS
PASS
```

**Invariants touched:**
- INV-09 — psycopg2 exceptions must be caught; raw detail must never reach the caller; detail must be the exact permitted literal

**Code review required:**
- Confirm all five connection parameters read from environment variables
- Confirm `except` block raises `HTTPException(500, "Internal server error")` as a string literal
- Confirm no f-string or concatenation includes the exception message in the detail

**Commit message:** `[S2.T3] add: database connection function — verification: PASS — invariants: INV-09`

---

### Task 2.4 — Write the API key authentication dependency

**Claude Code prompt:**
```
Add a verify_api_key dependency function to api/main.py.

Requirements:
- Function signature: async def verify_api_key(api_key: str = Header(None, alias="X-API-Key"))
- Reads the valid key from the API_KEY environment variable
- Comparison must use == only — not 'in', not startswith, not any partial match
- If the submitted key matches the environment key exactly, return without raising
- If the submitted key does not match — or is missing or empty — raise HTTPException
  with status_code=401 and detail="Unauthorized"
- The detail string is a static literal — not an f-string, not derived from the submitted key
- The submitted key value must not appear anywhere in the exception detail
- Do not attach this dependency to any route yet
```

**Test cases:**
- Correct key: function returns without raising
- Wrong key: raises HTTPException 401 with detail `"Unauthorized"`
- Missing key (None): raises HTTPException 401 with detail `"Unauthorized"`
- Empty string key: raises HTTPException 401 with detail `"Unauthorized"`
- Key that is a prefix of the valid key: raises HTTPException 401
- Valid key with trailing whitespace: raises HTTPException 401
- Detail string is identical across all failure cases

**Verification command:**
```bash
docker compose exec api python -c "
import asyncio, main
from fastapi import HTTPException
async def test():
    try:
        await main.verify_api_key('wrong-key')
    except HTTPException as e:
        print('PASS:', e.detail)
asyncio.run(test())"
```

**Expected output:**
```
PASS: Unauthorized
```

**Invariants touched:**
- INV-07 — authentication gate; dependency must raise before any route logic executes
- INV-08 — API key must not appear in any response
- INV-09 — detail string is a static literal; no internal detail reachable through auth errors
- INV-12 — 401 body is a static literal regardless of failure reason

**Code review required:**
- Confirm comparison uses `==` not `in`, `startswith`, or any partial match
- Confirm detail string is a literal `"Unauthorized"` — not an f-string
- Confirm submitted key value is not referenced in the HTTPException constructor
- Confirm function is NOT yet attached to any route
- Confirm `API_KEY` is read from environment, not hardcoded

**CD Challenge prompt:** What did you not test in Task 2.4? Focus on INV-07 and INV-08 — could an implementation pass all these cases while still violating either?

**Commit message:** `[S2.T4] add: api key auth dependency — verification: PASS — invariants: INV-07, INV-08, INV-09, INV-12`

---

### Session 2 Integration Check

```bash
docker compose up -d && sleep 5
# Health should return 200 with exactly {"status": "ok"}
curl -s http://localhost:8000/health
# Unauthenticated request — placeholder until T3.1 wires auth; confirm no 500
curl -s http://localhost:8000/customers/CUST-001
# Wrong key — placeholder until T3.1; confirm no 500
curl -s -H "X-API-Key: wrong" http://localhost:8000/customers/CUST-001
```

**Expected:** `/health` returns `{"status": "ok"}`. Customer requests return placeholder — no 500s.

---

## Session 3 — Customer Lookup Endpoint

**Goal:** Customer lookup endpoint with parameterised query, correct response shape, auth wired, and error handling verified.
**Branch:** `session/s03_lookup`

By the end of this session authenticated requests return customer data, unauthenticated requests return 401, and missing customers return 404.

---

### Task 3.1 — Wire auth dependency and implement customer lookup

**Claude Code prompt:**
```
Update the GET /customers/{customer_id} route in api/main.py.

Requirements:
- Add verify_api_key as a Depends() argument to the route
- Call get_db_connection() to open a psycopg2 connection
- Execute a parameterised SELECT query:
    SELECT customer_id, risk_tier, risk_factors
    FROM customer_risk_profiles
    WHERE customer_id = %s
  Pass customer_id as the query parameter — no string formatting or concatenation
- If a row is found, return JSON with exactly three fields:
    {"customer_id": "...", "risk_tier": "...", "risk_factors": [...]}
- If no row is found, raise HTTPException(404, "Customer not found")
- Close the connection in a finally block regardless of outcome
- Remove the placeholder return statement
```

**Test cases:**
- Authenticated request for existing customer returns 200 with correct shape
- Authenticated request for non-existent customer returns 404 with detail `"Customer not found"`
- Unauthenticated request returns 401 with detail `"Unauthorized"` — no DB interaction
- `risk_factors` in the response is a list, not a string
- `risk_factors` list contents match the database value for the same customer ID
- Response contains exactly `customer_id`, `risk_tier`, `risk_factors` — no extra fields

**Verification commands:**
```bash
# Existing customer — authenticated
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001

# Non-existent customer — authenticated
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-999

# No key — should return 401
curl -s http://localhost:8000/customers/CUST-001
```

**Expected outputs:**
```json
{"customer_id": "CUST-001", "risk_tier": "LOW", "risk_factors": ["..."]}
{"detail": "Customer not found"}
{"detail": "Unauthorized"}
```

**Invariants touched:**
- INV-01 — response values must match the database row exactly
- INV-02 — existing ID → 200; missing ID → 404; no other outcome
- INV-04 — query must use %s parameterisation; no string formatting
- INV-05 — response shape: exactly three fields with correct types
- INV-06 — risk_tier value passes through from DB unchanged
- INV-07 — auth dependency is now wired; unauthenticated requests rejected before DB access

**Code review required:**
- Confirm SQL query is a static string with a single `%s` — no f-strings, no `.format()`, no concatenation
- Confirm `verify_api_key` appears in the route signature as `Depends(verify_api_key)`
- Confirm `finally: conn.close()` is present
- Confirm response dict has exactly three keys

**Commit message:** `[S3.T1] add: customer lookup endpoint — verification: PASS — invariants: INV-01, INV-02, INV-04, INV-05, INV-06, INV-07`

---

### Task 3.2 — Verify response values match the database directly

**Claude Code prompt:**
```
No code changes in this task. This is a verification-only task.

Query the database directly and compare the output to the API response for the same
customer IDs. Record both outputs in VERIFICATION_RECORD.md.
```

**Test cases:**
- `risk_tier` in API response matches `risk_tier` column in DB row exactly for each ID
- `risk_factors` array in API response matches `risk_factors` array in DB row exactly
- `customer_id` in API response matches `customer_id` column in DB row exactly
- Verify one customer from each tier — confirm the ID-to-tier mapping matches the seed data before running

**Verification commands:**
```bash
# Direct database query — record this output first
docker compose exec db psql -U riskuser -d riskdb \
  -c "SELECT customer_id, risk_tier, risk_factors FROM customer_risk_profiles ORDER BY customer_id;"

# API responses — compare each field to the DB row above
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-004
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-007
```

**Note:** Before running, confirm which tier each ID belongs to from the seed data in init.sql. Record the expected tier for each ID in VERIFICATION_RECORD.md before fetching the API response.

**Invariants touched:**
- INV-01 — direct database-to-API comparison is the definitive verification of data correctness

**Commit message:** `[S3.T2] verify: data correctness against database — verification: PASS — invariants: INV-01`

---

### Task 3.3 — Verify database error handling

**Claude Code prompt:**
```
No code changes in this task. This is a verification-only task.

Stop the db container while the api container is running and confirm the error response
contains no internal detail.
```

**Verification commands:**
```bash
# Stop the database container
docker compose stop db

# Trigger a request — should return 500 with static literal
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001

# Confirm Content-Type is application/json on the error response
curl -si -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001 | grep -i content-type

# Restart the database
docker compose start db && sleep 8

# Confirm normal operation resumes
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
```

**Test cases:**
- Response when DB is down is 500
- Response body is exactly `{"detail": "Internal server error"}` — no variation
- Response `Content-Type` is `application/json`
- Response body contains no psycopg2 exception text, no table names, no connection details
- Normal operation resumes after DB restarts

**Invariants touched:**
- INV-09 — only pre-defined static strings in error responses

**Commit message:** `[S3.T3] verify: database error handling — verification: PASS — invariants: INV-09`

---

### Session 3 Integration Check

```bash
# Full happy path — all three tiers
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-004
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-007

# 404
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-999

# 401 — no key
curl -s http://localhost:8000/customers/CUST-001

# 401 — wrong key
curl -s -H "X-API-Key: wrong" http://localhost:8000/customers/CUST-001

# Health — confirm no extra fields
curl -s http://localhost:8000/health
```

**Expected:** All three tiers return correct data. 404 returns static literal. Both 401 cases return identical static literal. Health returns `{"status": "ok"}` only.

---

## Session 4 — Browser UI and Error State Tests

**Goal:** Browser UI served from the FastAPI container. Automated tests for error states.
**Branch:** `session/s04_ui`

By the end of this session operations staff can look up a customer from a browser.

---

### Task 4.1 — Implement the browser UI

**Claude Code prompt:**
```
Replace the placeholder HTMLResponse in GET / with a complete browser UI.

Requirements:
- Return an HTMLResponse containing a complete HTML page inline in main.py
- The page contains:
    - A text input for customer_id
    - A submit button
    - A result display area
- On submit, the JavaScript makes a fetch call to /customers/{customer_id}
  using a relative path — not an absolute URL with a hardcoded host
- The fetch call must include the X-API-Key header
- The JavaScript renders the API response directly into the result area:
    - Display customer_id, risk_tier, and risk_factors exactly as returned
    - No remapping of tier strings (no switch statement, no label map)
    - No reordering or filtering of risk_factors
    - Display the 401 detail string if returned
    - Display the 404 detail string if returned
    - Display the 500 detail string if returned
- No external scripts, no CDN links, no frontend framework
- All HTML, CSS, and JavaScript in the single inline string
```

**Test cases:**
- `GET /` returns 200 with `Content-Type: text/html`
- Page contains a text input and a submit button
- JavaScript fetch target is a relative path `/customers/${id}` — not a hardcoded host
- JavaScript fetch call includes the `X-API-Key` header
- No external script tags or CDN references in the HTML
- For a valid customer: `customer_id`, `risk_tier`, and `risk_factors` are all displayed
- For a 404: the detail string `"Customer not found"` is displayed
- For a 401: the detail string `"Unauthorized"` is displayed
- DOM values match API response values exactly — no transformation

**Verification commands:**
```bash
# Confirm page loads
curl -s http://localhost:8000/ | grep -i "<input"

# Confirm no external script references
curl -s http://localhost:8000/ | grep -i "src=" | grep -v "localhost"

# Confirm relative fetch path
curl -s http://localhost:8000/ | grep -i "customers/"
```

**Invariants touched:**
- INV-11 — UI renders API values without transformation

**Code review required:**
- Read the JavaScript. Confirm no switch statements on tier values, no label maps, no conditional display logic that modifies what the API returned
- Confirm fetch URL is a relative path `/customers/${id}` — not an absolute URL
- Confirm `X-API-Key` header is included in the fetch call
- Confirm all HTML/JS is inline — no StaticFiles mount

**CD Challenge prompt:** What did you not test in Task 4.1? Focus on INV-11 — could an implementation render the correct values in some cases while transforming them in others?

**Commit message:** `[S4.T1] add: browser UI — verification: PASS — invariants: INV-11`

---

### Task 4.2 — Write automated error state tests

**Claude Code prompt:**
```
Create api/test_errors.py with automated tests for error states.

Requirements — use Python's built-in unittest and the requests library:

Test cases to cover:
1. No API key → 401, detail == "Unauthorized"
2. Wrong API key → 401, detail == "Unauthorized"
3. Empty API key header → 401, detail == "Unauthorized"
4. Missing customer ID (non-existent) → 404, detail == "Customer not found"
5. Both 401 cases (wrong key and no key) return identical response bodies

Read API_KEY and BASE_URL from environment variables.
BASE_URL default: http://localhost:8000

Do not test the happy path in this file — that is covered by manual verification records.
```

**Test cases:**
- All five test cases pass
- No test reads from the database directly
- Test file is self-contained — no fixtures beyond environment variables

**Verification command:**
```bash
cd customer-risk-api && python -m pytest api/test_errors.py -v
```

**Expected output:** 5 tests collected, 5 passed.

**Invariants touched:**
- INV-02 — missing customer returns 404 with correct literal
- INV-07 — unauthenticated requests rejected
- INV-08 — 401 detail does not vary or expose key
- INV-12 — 401 body is identical across all failure reasons

**Commit message:** `[S4.T2] add: error state tests — verification: PASS — invariants: INV-02, INV-07, INV-08, INV-12`

---

### Session 4 Integration Check

```bash
# Automated tests
cd customer-risk-api && python -m pytest api/test_errors.py -v

# Manual UI check
echo "Open http://localhost:8000 in a browser"
echo "Query CUST-001, CUST-004, CUST-007 — confirm values match direct API responses"
echo "Query CUST-999 — confirm 'Customer not found' displayed"
```

---

## Session 5 — Hardening, Injection Tests, Full Invariant Run

**Goal:** SQL injection tests, full invariant verification script, README.
**Branch:** `session/s05_harden`

This session ends with the full invariant script run from a cold start. Everything automated must pass.

---

### Task 5.1 — Write SQL injection tests

**Claude Code prompt:**
```
Create api/test_injection.py with SQL injection tests.

Requirements — use Python's built-in unittest and the requests library:

Before any requests: record the exact row count in customer_risk_profiles.

Test the following customer_id values — each should return 404, not 500 or 200:
1. "'; DROP TABLE customer_risk_profiles; --"
2. "' OR '1'='1"
3. "' UNION SELECT null, null, null --"
4. "1; SELECT * FROM customer_risk_profiles"
5. A 500-character string of repeated SQL keywords

After all requests: query the database and assert the row count equals the count
recorded before — not just "count > 0", but the exact pre-test number.

Read API_KEY, BASE_URL, and POSTGRES_* from environment variables.
```

**Test cases:**
- All 5 injection strings return 404
- None return 500 (which would indicate an unhandled exception)
- None return 200 (which would indicate a match)
- Row count after all requests equals the exact row count recorded before the test run

**Verification command:**
```bash
cd customer-risk-api && python -m pytest api/test_injection.py -v
```

**Expected output:** All tests pass.

**Invariants touched:**
- INV-03 — no write operations reachable through any endpoint
- INV-04 — parameterised queries prevent injection

**Commit message:** `[S5.T1] add: SQL injection tests — verification: PASS — invariants: INV-03, INV-04`

---

### Task 5.2 — Write the full invariant verification script

**Claude Code prompt:**
```
Create api/test_invariants.py — a single script that verifies every automated invariant.

INV-01: For CUST-001, CUST-004, CUST-007 — fetch API response and compare to direct
        DB query. All three fields must match exactly.

INV-02: Existing ID returns 200. Non-existent ID returns 404. No other codes for these cases.

INV-03: Record row count before a full set of API requests. Assert exact count after.

INV-04: Run the injection strings from test_injection.py. All return 404 or 401, never 500.

INV-05: For every 200 response — confirm exactly three keys: customer_id, risk_tier,
        risk_factors. Confirm types: string, string, list.

INV-06: For every 200 response — confirm risk_tier is one of {"LOW", "MEDIUM", "HIGH"}.

INV-07: Request without key returns 401. Row count is unchanged after the request.
        NOTE: this is a proxy check only — code review of verify_api_key is the
        definitive confirmation that no DB interaction occurs.

INV-08: 401 detail string does not contain the submitted key value.

INV-09: Stop the DB container. Make a request. Confirm response body is exactly
        {"detail": "Internal server error"}. Sleep 10 seconds after restarting DB
        before continuing to the next test.

INV-12: Wrong key and missing key return identical response bodies.

INV-13: GET /health response body contains exactly one key: "status".
        No customer data, no row counts, no additional fields.

INV-10 and INV-11 are manual — see notes below.

Read API_KEY, BASE_URL, POSTGRES_* from environment variables.
Run as: python -m pytest api/test_invariants.py -v
```

**Verification command:**
```bash
cd customer-risk-api && python -m pytest api/test_invariants.py -v
```

**Expected output:** All automated invariant tests pass.

**Manual checks — record results in VERIFICATION_RECORD.md:**

INV-10 — Operational isolation:
```bash
grep -i "external" customer-risk-api/docker-compose.yml \
  || echo "No external networks — PASS"
grep -E "import requests|import httpx|import urllib" customer-risk-api/api/main.py \
  || echo "No outbound imports — PASS"
```

INV-11 — UI fidelity:
- Open browser to http://localhost:8000
- Query CUST-001
- In devtools console: `fetch('/customers/CUST-001', {headers: {'X-API-Key': 'your-key'}}).then(r=>r.json()).then(console.log)`
- Compare JSON response fields to DOM values — they must be identical

**Note on INV-07:** The automated test is a proxy only. The definitive check is code review — confirm `verify_api_key` is the first thing called in the route and that no DB connection is opened before it raises.

**Invariants touched:** INV-01 through INV-13 (INV-10 and INV-11 manual).

**Commit message:** `[S5.T2] add: full invariant verification script — verification: PASS — invariants: INV-01 through INV-13`

---

### Task 5.3 — Write README.md

**Claude Code prompt:**
```
Write README.md for the Customer Risk API.

Required sections:
1. What it is — one paragraph
2. Prerequisites — Docker Desktop, git, a .env file
3. Setup — exact commands:
   cp .env.example .env
   # edit .env with your values
   docker compose up -d
4. Usage — curl examples for:
   - Health check
   - Authenticated customer lookup (existing)
   - Authenticated customer lookup (not found)
   - Unauthenticated request (expected 401)
5. Teardown — docker compose down -v with an explicit warning that omitting -v
   leaves the data volume and bypasses seeding on the next up
6. Stack — list the four components

Do not include internal architecture detail, invariant references, or session notes.
Curl examples must use $API_KEY not a hardcoded value.
```

**Test cases:**
- README contains `docker compose down -v` with the `-v` flag warning
- Curl examples use `$API_KEY` not a hardcoded value
- README does not reference PBVI, sessions, or internal planning artifacts

**Verification command:**
```bash
grep "\-v" customer-risk-api/README.md && echo "Teardown flag documented — PASS"
```

**Invariants touched:** None directly.

**Commit message:** `[S5.T3] add: README — verification: PASS`

---

### Session 5 Integration Check — Final Gate

Run from a completely clean state. This is the acceptance gate.

```bash
# Full teardown — -v flag is mandatory
cd customer-risk-api
docker compose down -v

# Cold start
docker compose up -d
sleep 10

# Full automated invariant run
python -m pytest api/test_invariants.py api/test_errors.py api/test_injection.py -v

# Manual: INV-10
grep -i "external" docker-compose.yml || echo "No external networks — PASS"
grep -E "import requests|import httpx|import urllib" api/main.py \
  || echo "No outbound imports — PASS"

# Manual: INV-11
echo "Open http://localhost:8000 — verify UI fidelity for CUST-001, CUST-004, CUST-007"
```

**Acceptance criteria:** All automated tests pass from cold start. INV-10 and INV-11 manual checks recorded in VERIFICATION_RECORD.md. No 500s in any test output.

---

## Invariant Touch Map

| Invariant | Tasks that touch it |
|---|---|
| INV-01 | S1.T2, S3.T1, S3.T2, S5.T2 |
| INV-02 | S1.T3, S3.T1, S4.T2, S5.T2 |
| INV-03 | S1.T2, S5.T1, S5.T2 |
| INV-04 | S3.T1, S5.T1, S5.T2 |
| INV-05 | S1.T2, S3.T1, S5.T2 |
| INV-06 | S1.T2, S3.T1, S5.T2 |
| INV-07 | S1.T3, S2.T4, S3.T1, S4.T2, S5.T2 |
| INV-08 | S2.T4, S4.T2, S5.T2 |
| INV-09 | S2.T3, S2.T4, S3.T3, S5.T2 |
| INV-10 | S1.T3, S5.T2 (manual) |
| INV-11 | S4.T1, S5.T2 (manual) |
| INV-12 | S2.T4, S4.T2, S5.T2 |
| INV-13 | S2.T2, S5.T2 |

---

*DataGrokr Engineering · PBVI Practitioner Series · 2026*