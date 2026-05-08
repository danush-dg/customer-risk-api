# Execution_Plan.md — Customer Risk API
*Phase 3 · DataGrokr Engineering · 2026*

---

## How to read this plan

Each session is a self-contained unit of work with a defined gate condition.
Each task within a session is atomic: it has one prompt for Claude Code, explicit
test cases, a runnable verification command, and the invariants it touches.

**Prediction rule:** Write your expected outcome before running any verification
command. A result read before a prediction is formed is observation, not
verification.

**Gate rule:** Claude never declares a gate passed. The engineer signs off at each
session gate before proceeding.

**Conflict rule:** If any task conflicts with a named invariant, the invariant wins.
Flag the conflict; never resolve it silently.

---

## Session Map

| Session | Scope | Gate condition |
|---|---|---|
| S1 | Scaffold + database layer | `docker compose up` starts cleanly; seed data verifiable via psql |
| S2 | API core — auth, routes, schemas | All endpoints return correct status codes; all 18 invariants covered in code review |
| S3 | Injection hardening + error surfaces | Three injection strings produce no DB change; DB-down returns generic 500 |
| S4 | UI layer | UI renders verbatim values; all error paths display raw detail strings |
| S5 | Integration + invariant sweep | Full end-to-end test against all 18 invariants; no open gaps |

---

## Session 1 — Scaffold and Database Layer

**Goal:** Produce a running two-service Compose stack with a correctly seeded
Postgres database. No application logic. Gate is `docker compose up` completing
without error and seed data verifiable directly via psql.

---

### Task 1.1 — Repo scaffold and .env configuration

**Claude Code prompt:**

```
Create the top-level project directory structure for the Customer Risk API.
The structure must be:

customer-risk-api/
  docker-compose.yml        (empty stub — two services: db and api)
  .env.example              (contains API_KEY=<your-key-here> and POSTGRES_PASSWORD=<your-password-here>)
  .gitignore                (must include .env on its own line)
  db/
    init.sql                (empty stub)
  api/
    Dockerfile              (empty stub)
    requirements.txt        (empty stub)
    app/
      __init__.py
      main.py               (empty stub)
      router.py             (empty stub)
      auth.py               (empty stub)
      db.py                 (empty stub)
      schemas.py            (empty stub)
  static/
    index.html              (empty stub)

Do not write any logic. Stubs only. Create a README.md at the root with a single
line: "Customer Risk API — see ARCHITECTURE.md for design decisions."
```

**Test cases:**

- T1.1.1: All files and directories listed above exist.
- T1.1.2: `.gitignore` contains the line `.env` exactly.
- T1.1.3: `.env.example` exists and `.env` does not exist.
- T1.1.4: `git ls-files | grep -E '^\.env$'` returns nothing after `git init && git add .`.

**Verification command:**

```bash
find customer-risk-api -type f | sort
git -C customer-risk-api ls-files | grep -E '^\.env$' && echo "FAIL — .env tracked" || echo "PASS — .env not tracked"
```

**Invariants touched:** INV-12

---

### Task 1.2 — Postgres service definition in docker-compose.yml

**Claude Code prompt:**

```
Write the `db` service block in docker-compose.yml for the Customer Risk API.

Requirements:
- Image: postgres:15
- Environment variables sourced from .env: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- Mount db/init.sql into /docker-entrypoint-initdb.d/init.sql (read-only)
- Expose no host port (internal network only)
- Define a healthcheck: pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}
  with interval 5s, timeout 3s, retries 5, start_period 10s
- Connect to a named internal network: risk-net

Do not write the api service yet. Do not write init.sql content yet.
```

**Test cases:**

- T1.2.1: `docker compose config` parses without error.
- T1.2.2: The `db` service has no `ports` key (not exposed to host).
- T1.2.3: The healthcheck block is present with the specified parameters.
- T1.2.4: The network named `risk-net` is declared in the top-level `networks` block.

**Verification command:**

```bash
docker compose config
docker compose config | grep -A5 "healthcheck"
docker compose config | grep "ports" && echo "WARN — db ports exposed" || echo "PASS — db not exposed"
```

**Invariants touched:** INV-15, R-4 (startup race mitigation)

---

### Task 1.3 — Database schema and seed data in init.sql

**Claude Code prompt:**

```
Write db/init.sql for the Customer Risk API.

Requirements:
1. Create table customer_risk_profiles with columns:
   - customer_id VARCHAR(50) PRIMARY KEY
   - risk_tier VARCHAR(10) NOT NULL CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))
   - risk_factors TEXT[] NOT NULL

2. Seed exactly 9 customers: 3 per tier (LOW, MEDIUM, HIGH).
   Customer IDs must follow the format CUST-001 through CUST-009.
   Risk factors must be plain strings (no structured objects).
   Each customer must have between 1 and 4 risk factors.
   Choose plausible financial risk factor strings (e.g. 'late payment history',
   'high debt-to-income ratio', 'new account opened recently').

3. No triggers. No stored procedures. No functions. No additional tables.

Constraints:
- The CHECK constraint on risk_tier must be present on the column definition.
- TEXT[] must be the exact column type for risk_factors.
- No INSERT may produce a risk_tier value outside LOW / MEDIUM / HIGH.
```

**Test cases:**

- T1.3.1: `SELECT COUNT(*) FROM customer_risk_profiles` returns 9.
- T1.3.2: `SELECT COUNT(*) FROM customer_risk_profiles WHERE risk_tier = 'LOW'` returns 3.
- T1.3.3: `SELECT COUNT(*) FROM customer_risk_profiles WHERE risk_tier = 'MEDIUM'` returns 3.
- T1.3.4: `SELECT COUNT(*) FROM customer_risk_profiles WHERE risk_tier = 'HIGH'` returns 3.
- T1.3.5: `INSERT INTO customer_risk_profiles VALUES ('TEST-99', 'low', '{}')` raises a constraint violation.
- T1.3.6: Static review — no `CREATE TRIGGER` or `CREATE FUNCTION` in init.sql.

**Verification command:**

```bash
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM customer_risk_profiles;"
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT risk_tier, COUNT(*) FROM customer_risk_profiles GROUP BY risk_tier;"
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "INSERT INTO customer_risk_profiles VALUES ('TEST-99', 'low', '{}');" 2>&1 | grep -i "violates check constraint" && echo "PASS — CHECK constraint active" || echo "FAIL — CHECK constraint missing"
grep -iE "CREATE TRIGGER|CREATE FUNCTION" db/init.sql && echo "FAIL — trigger or function present" || echo "PASS — no triggers or functions"
```

**Invariants touched:** INV-01 (CHECK constraint), INV-05 (INV-06 static review), INV-06, A-2 (risk_factors as TEXT[]), A-5 (3 per tier)

---

### Task 1.4 — API Dockerfile and requirements.txt

**Claude Code prompt:**

```
Write api/Dockerfile and api/requirements.txt for the Customer Risk API.

Dockerfile requirements:
- Base image: python:3.11-slim
- Working directory: /app
- Copy requirements.txt and install dependencies before copying app code
  (layer caching)
- Copy the app/ directory and the static/ directory into /app
- Expose port 8000
- CMD must start uvicorn: uvicorn app.main:app --host 0.0.0.0 --port 8000

requirements.txt must pin exact versions for:
- fastapi
- uvicorn[standard]
- psycopg2-binary
- pydantic

No other dependencies. No ORM libraries. No requests or httpx.
```

**Test cases:**

- T1.4.1: `docker build -t risk-api-test ./api` completes without error.
- T1.4.2: Static review of requirements.txt — no `sqlalchemy`, `requests`, `httpx`, `aiohttp` present.
- T1.4.3: Static review of Dockerfile — CMD uses `uvicorn app.main:app`.

**Verification command:**

```bash
docker build -t risk-api-test ./api && echo "PASS — build succeeded" || echo "FAIL — build failed"
grep -iE "sqlalchemy|requests|httpx|aiohttp" api/requirements.txt && echo "FAIL — prohibited dependency present" || echo "PASS — no prohibited dependencies"
```

**Invariants touched:** INV-15 (no requests/httpx in deps), stack constraint (no ORM)

---

### Task 1.5 — API service definition and Compose dependency wiring

**Claude Code prompt:**

```
Add the `api` service to docker-compose.yml for the Customer Risk API.

Requirements:
- Build context: ./api
- Environment variables from .env: API_KEY, POSTGRES_HOST=db, POSTGRES_PORT=5432,
  POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- Expose port 8000 on the host: "8000:8000"
- depends_on: db with condition: service_healthy
- Connect to the risk-net network
- Define a healthcheck: curl -f http://localhost:8000/health
  with interval 10s, timeout 5s, retries 3, start_period 15s

Do not change the db service block.
```

**Test cases:**

- T1.5.1: `docker compose config` parses without error.
- T1.5.2: The `api` service has `depends_on.db.condition: service_healthy`.
- T1.5.3: Host port 8000 is mapped to container port 8000.
- T1.5.4: Both services are on `risk-net`.

**Verification command:**

```bash
docker compose config | grep -A3 "depends_on"
docker compose config | grep "8000"
```

**Invariants touched:** R-4 (startup race), INV-15

---

### Session 1 Gate

**Gate condition:** `docker compose up -d` starts both services, `db` passes its
healthcheck, and psql queries return the expected 9-row seed data. The API
container may fail its healthcheck (main.py is a stub) — this is acceptable at
this gate.

**Sign-off checklist:**
- [ ] `docker compose ps` shows `db` as healthy
- [ ] Seed data count verified: 9 rows, 3 per tier
- [ ] CHECK constraint rejects `'low'` — verified
- [ ] No triggers or functions in init.sql — reviewed
- [ ] `.env` not tracked in git — verified
- [ ] `.env.example` present — verified

---

## Session 2 — API Core: Auth, Routes, Schemas

**Goal:** Implement the four application modules (`schemas.py`, `auth.py`, `db.py`,
`router.py`) and wire `main.py`. All endpoints must return correct status codes.
All 18 invariants must be addressable by code review at session close.

---

### Task 2.1 — Pydantic schemas

**Claude Code prompt:**

```
Write api/app/schemas.py for the Customer Risk API.

Requirements:
1. Define CustomerResponse with fields:
   - customer_id: str
   - risk_tier: str
   - risk_factors: list[str]
   model_config = ConfigDict(extra='forbid')

2. Define HealthResponse with fields:
   - status: str
   model_config = ConfigDict(extra='forbid')

3. No other models. No imports beyond pydantic.
4. Both models must use ConfigDict(extra='forbid') — not extra='ignore',
   not extra='allow'.

Import pattern: from pydantic import BaseModel, ConfigDict
```

**Test cases:**

- T2.1.1: `CustomerResponse(customer_id='CUST-001', risk_tier='HIGH', risk_factors=['a'])` instantiates without error.
- T2.1.2: `CustomerResponse(customer_id='CUST-001', risk_tier='HIGH', risk_factors=['a'], extra_field='x')` raises `ValidationError`.
- T2.1.3: `HealthResponse(status='ok')` instantiates without error.
- T2.1.4: `HealthResponse(status='ok', version='1.0')` raises `ValidationError`.
- T2.1.5: Static review — both models have `model_config = ConfigDict(extra='forbid')`.

**Verification command:**

```bash
docker compose exec api python -c "
from app.schemas import CustomerResponse, HealthResponse
from pydantic import ValidationError
# T2.1.1
r = CustomerResponse(customer_id='CUST-001', risk_tier='HIGH', risk_factors=['a'])
print('T2.1.1 PASS')
# T2.1.2
try:
    CustomerResponse(customer_id='CUST-001', risk_tier='HIGH', risk_factors=['a'], extra_field='x')
    print('T2.1.2 FAIL')
except ValidationError:
    print('T2.1.2 PASS')
# T2.1.3
HealthResponse(status='ok')
print('T2.1.3 PASS')
# T2.1.4
try:
    HealthResponse(status='ok', version='1.0')
    print('T2.1.4 FAIL')
except ValidationError:
    print('T2.1.4 PASS')
"
```

**Invariants touched:** INV-07 (extra='forbid'), INV-10 (HealthResponse model)

---

### Task 2.2 — API key authentication dependency

**Claude Code prompt:**

```
Write api/app/auth.py for the Customer Risk API.

Requirements:
1. Import: from fastapi import Header, HTTPException
2. Import: from os import environ

3. Define a single function: verify_api_key(api_key: str = Header(default=None, alias="X-API-Key"))

4. The function must:
   a. Read the expected key from environ["API_KEY"]
   b. If api_key is None OR api_key != expected key:
      raise HTTPException(status_code=401, detail="Unauthorized")
   c. The detail string must be the string literal "Unauthorized" — not an
      f-string, not any expression referencing api_key or the environment variable.
   d. Return nothing (implicitly returns None on success).

5. No other functions. No logging. No print statements.

Critical: Header(default=None) is required. Do NOT use Header() without a default.
A missing header must arrive as None and trigger the 401 — not a 422.
```

**Test cases:**

- T2.2.1: Request with no `X-API-Key` header returns 401, not 422.
- T2.2.2: Request with wrong key returns 401.
- T2.2.3: Request with empty string key returns 401.
- T2.2.4: Request with correct key passes the dependency (no exception raised).
- T2.2.5: Request with correct key in `Authorization: Bearer` header (no `X-API-Key`) returns 401.
- T2.2.6: Static review — detail value is the string literal `"Unauthorized"`, not an f-string.

**Verification command:**

```bash
# After full stack is up (Task 2.5 complete):
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/customers/CUST-001
# Expected: 401

curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: wrongkey" http://localhost:8000/customers/CUST-001
# Expected: 401

curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: " http://localhost:8000/customers/CUST-001
# Expected: 401

curl -s -H "Authorization: Bearer $API_KEY" http://localhost:8000/customers/CUST-001
# Expected: 401 body, not 422

grep -E 'f".*api_key|f".*API_KEY' api/app/auth.py && echo "FAIL — f-string in detail" || echo "PASS — no f-string"
```

**Invariants touched:** INV-09 (401 not 422), INV-11 (key never in response)

---

### Task 2.3 — Database access layer

**Claude Code prompt:**

```
Write api/app/db.py for the Customer Risk API.

Requirements:
1. Imports: psycopg2, os, fastapi.HTTPException

2. Define one function: get_customer(customer_id: str) -> dict | None

3. The function must:
   a. Open a new psycopg2 connection using these env vars:
      host=os.environ["POSTGRES_HOST"], port=os.environ["POSTGRES_PORT"],
      dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
      password=os.environ["POSTGRES_PASSWORD"]
   b. Execute: SELECT customer_id, risk_tier, risk_factors FROM customer_risk_profiles
      WHERE customer_id = %s
      Pass (customer_id,) as the values tuple. No string formatting. No concatenation.
   c. Fetch one row. If no row: return None.
   d. If a row: return {"customer_id": row[0], "risk_tier": row[1], "risk_factors": row[2]}
   e. Always close the connection in a finally block.

4. Wrap the entire body (including connection open) in a two-clause try/except:
   - except psycopg2.Error: raise HTTPException(status_code=500, detail="Internal server error")
   - except Exception: raise HTTPException(status_code=500, detail="Internal server error")
   Both clauses must use the string literal "Internal server error".
   Neither clause may reference the caught exception variable (no str(e), no e.args).

5. No other functions. No connection pool. No SQLAlchemy.
```

**Test cases:**

- T2.3.1: `get_customer("CUST-001")` returns a dict with keys `customer_id`, `risk_tier`, `risk_factors`.
- T2.3.2: `get_customer("CUST-NONE")` returns `None`.
- T2.3.3: With DB stopped, `get_customer("CUST-001")` raises `HTTPException(500)` with `detail="Internal server error"`.
- T2.3.4: Static review — no string formatting (`%` or `.format()` or f-string) used to build the SQL query string.
- T2.3.5: Static review — both `except` clauses present; neither references the caught exception variable.
- T2.3.6: Static review — `finally` block closes connection.

**Verification command:**

```bash
docker compose exec api python -c "
from app.db import get_customer
r = get_customer('CUST-001')
assert r is not None and 'risk_tier' in r, 'T2.3.1 FAIL'
print('T2.3.1 PASS:', r)
r2 = get_customer('CUST-NONE')
assert r2 is None, 'T2.3.2 FAIL'
print('T2.3.2 PASS')
"
grep -E '%s.*format|f".*SELECT|f".*WHERE' api/app/db.py && echo "FAIL — string formatting in SQL" || echo "PASS — parameterised only"
grep -E 'str\(e\)|e\.args|f".*{e}' api/app/db.py && echo "FAIL — exception variable in detail" || echo "PASS — no exception variable in detail"
```

**Invariants touched:** INV-03 (parameterised queries), INV-05, INV-13, INV-14

---

### Task 2.4 — Route definitions

**Claude Code prompt:**

```
Write api/app/router.py for the Customer Risk API.

Requirements:
1. Create an APIRouter instance: router = APIRouter()

2. Define GET /health:
   - No authentication dependency
   - response_model=HealthResponse
   - Handler returns HealthResponse(status="ok")
   - Handler return type annotation: -> HealthResponse

3. Define GET /customers/{customer_id}:
   - Depends on verify_api_key (imported from auth)
   - response_model=CustomerResponse
   - Handler return type annotation: -> CustomerResponse
   - Call db.get_customer(customer_id)
   - If None: raise HTTPException(status_code=404, detail="Customer not found")
     The detail must be the string literal "Customer not found" — not an f-string,
     not any expression referencing customer_id.
   - If found: return CustomerResponse(**result)

4. No other routes. No GET /debug, no POST routes, no PUT routes.

Imports needed: fastapi (APIRouter, Depends, HTTPException), app.auth, app.db, app.schemas.
```

**Test cases:**

- T2.4.1: `GET /health` with no key returns 200 with body `{"status": "ok"}`.
- T2.4.2: `GET /customers/CUST-001` with valid key returns 200 with all three fields.
- T2.4.3: `GET /customers/CUST-NONE` with valid key returns 404 with body `{"detail": "Customer not found"}`.
- T2.4.4: `GET /customers/CUST-001` with no key returns 401.
- T2.4.5: Static review — `GET /customers/{customer_id}` decorator includes `response_model=CustomerResponse`.
- T2.4.6: Static review — handler signature is `def get_customer(...) -> CustomerResponse:`.
- T2.4.7: Static review — 404 detail is a string literal, not an f-string referencing `customer_id`.

**Verification command:**

```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}

curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
# Expected: {"customer_id":"CUST-001","risk_tier":"...","risk_factors":[...]}

curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-NONE
# Expected: {"detail":"Customer not found"}

curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/customers/CUST-001
# Expected: 401

grep -E 'f".*customer_id|detail.*{customer' api/app/router.py && echo "FAIL — f-string in 404 detail" || echo "PASS"
```

**Invariants touched:** INV-03, INV-04, INV-07, INV-08, INV-09, INV-10, INV-17

---

### Task 2.5 — Application entry point and startup validation

**Claude Code prompt:**

```
Write api/app/main.py for the Customer Risk API.

Requirements:
1. On startup — before creating the FastAPI app — validate the API_KEY environment variable:
   a. Read os.environ.get("API_KEY", "")
   b. If the value is absent, empty, or fewer than 16 characters:
      print an explicit error message identifying the problem to stderr
      call sys.exit(1)
   This validation must execute at module import time (top-level code, not inside
   a function or event handler).

2. Create the FastAPI app instance: app = FastAPI()

3. Mount /static as StaticFiles from the "static" directory with name="static".

4. Add a route: GET / returns the index.html file from the static directory.
   Use FileResponse("static/index.html").

5. Include the router from app.router with no prefix.

6. The file must contain no business logic beyond mounting and including.
   No route handlers beyond GET /.

Imports needed: os, sys, fastapi (FastAPI, responses), fastapi.staticfiles,
app.router.
```

**Test cases:**

- T2.5.1: Starting container with `API_KEY=` (empty) exits non-zero and does not bind port 8000.
- T2.5.2: Starting container with `API_KEY=tooshort` (< 16 chars) exits non-zero.
- T2.5.3: Starting container with a valid 16+ char key starts normally.
- T2.5.4: `GET /` returns 200 with HTML content.
- T2.5.5: `GET /notaroute` returns 404.
- T2.5.6: Static review — validation executes before `FastAPI()` instantiation.

**Verification command:**

```bash
# T2.5.1 — test with empty key
docker compose run --rm -e API_KEY= api python -m app.main 2>&1 | head -5
echo "Exit code: $?"

# T2.5.2 — test with short key
docker compose run --rm -e API_KEY=tooshort api python -m app.main 2>&1 | head -5

# T2.5.4 — UI served
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
# Expected: 200

# T2.5.5 — unknown route
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/notaroute
# Expected: 404
```

**Invariants touched:** INV-17, INV-18

---

### Task 2.6 — Route enumeration unit test

**Claude Code prompt:**

```
Write a standalone Python test file at api/tests/test_routes.py for the
Customer Risk API.

Requirements:
1. Import the FastAPI app from app.main.
2. Use TestClient from starlette.testclient.
3. Write one test function: test_route_set_is_complete()
   - Enumerate all routes: paths = {r.path for r in app.routes}
   - Assert the set contains exactly: '/', '/health', '/customers/{customer_id}'
     (plus any FastAPI framework routes for OpenAPI: '/openapi.json', '/docs', '/redoc')
   - Fail with a descriptive message if any unexpected route is present.

4. Write one test function: test_post_customers_returns_405()
   - POST to /customers/CUST-001 — assert 405.

5. Write one test function: test_get_admin_returns_404()
   - GET /admin — assert 404.

No external dependencies beyond starlette and fastapi.
Set API_KEY to a 20-character string in the test environment to pass startup validation.
```

**Test cases:**

- T2.6.1: `pytest api/tests/test_routes.py` passes all three tests.
- T2.6.2: Adding a `GET /debug` route to router.py causes `test_route_set_is_complete` to fail.

**Verification command:**

```bash
API_KEY=testkeytestkeytestkey pytest api/tests/test_routes.py -v
```

**Invariants touched:** INV-17

---

### Session 2 Gate

**Sign-off checklist:**
- [ ] `GET /health` returns `{"status": "ok"}` with no API key
- [ ] `GET /customers/CUST-001` with valid key returns all three fields
- [ ] `GET /customers/CUST-NONE` returns exactly `{"detail": "Customer not found"}`
- [ ] All auth test cases pass (no key → 401, wrong header name → 401 not 422)
- [ ] `schemas.py` — both models have `extra='forbid'` — reviewed
- [ ] `router.py` — `response_model=CustomerResponse` on route decorator — reviewed
- [ ] `router.py` — handler return type `-> CustomerResponse` — reviewed
- [ ] `auth.py` — detail is string literal, not f-string — reviewed
- [ ] `router.py` — 404 detail is string literal, not f-string — reviewed
- [ ] `db.py` — parameterised queries only, no string formatting — reviewed
- [ ] `db.py` — dual-clause except, neither references exception variable — reviewed
- [ ] `main.py` — startup validation before `FastAPI()` — reviewed
- [ ] Route enumeration test passes

---

## Session 3 — Injection Hardening and Error Surfaces

**Goal:** Confirm the three specified injection strings produce no database change.
Confirm DB-down returns a generic 500 with no internal state. Confirm no
psycopg2 exception reaches FastAPI's default handler.

---

### Task 3.1 — SQL injection confirmation tests

**Claude Code prompt:**

```
Write a test file at api/tests/test_injection.py for the Customer Risk API.

The test must submit the following three customer_id values as path parameters to
GET /customers/{customer_id} with a valid API key, and after each call verify that
the database is unchanged.

Injection strings (URL-encode as needed):
1. '; DROP TABLE customer_risk_profiles; --
2. 1 OR 1=1
3. CUST-001'; UPDATE customer_risk_profiles SET risk_tier='LOW' WHERE '1'='1

For each injection string:
- Submit the request — assert the response is either 200 or 404 (both are valid;
  the ID simply doesn't match any row)
- Assert the response is NOT 500
- After the call: connect to the database directly and run
  SELECT COUNT(*) FROM customer_risk_profiles — assert the result is 9
- After the call: SELECT risk_tier FROM customer_risk_profiles WHERE customer_id = 'CUST-007'
  (a known HIGH tier customer) — assert the tier has not changed

Note: these tests are confirmatory. The primary defence is the parameterised query
in db.py, verified in Task 2.3. These tests confirm that defence is active.
```

**Test cases:**

- T3.1.1: Injection string 1 — row count remains 9 after call.
- T3.1.2: Injection string 2 — row count remains 9 after call.
- T3.1.3: Injection string 3 — CUST-007 risk_tier unchanged after call.
- T3.1.4: None of the three calls return 500.

**Verification command:**

```bash
API_KEY=$API_KEY pytest api/tests/test_injection.py -v
# Then manually confirm:
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM customer_risk_profiles;"
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT risk_tier FROM customer_risk_profiles WHERE customer_id = 'CUST-007';"
```

**Invariants touched:** INV-05

---

### Task 3.2 — DB-down error surface test

**Claude Code prompt:**

```
Write a test function in api/tests/test_error_surfaces.py for the Customer Risk API.

test_db_down_returns_generic_500():
  1. Stop the db container (subprocess or Docker SDK call).
  2. Call GET /customers/CUST-001 with a valid API key.
  3. Assert HTTP 500.
  4. Assert the response body is exactly {"detail": "Internal server error"}.
  5. Assert the response body does not contain any of these strings:
     - "db" (hostname)
     - "5432" (port)
     - "psycopg2"
     - "OperationalError"
     - "password"
  6. Restart the db container and wait for it to be healthy before test teardown.

This test requires the full stack running. Mark it with @pytest.mark.integration.
```

**Test cases:**

- T3.2.1: Response is HTTP 500.
- T3.2.2: Body is exactly `{"detail": "Internal server error"}`.
- T3.2.3: Body contains none of the five prohibited strings.

**Verification command:**

```bash
docker compose stop db
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
# Expected: {"detail":"Internal server error"} with status 500
docker compose start db
```

**Invariants touched:** INV-13, INV-14

---

### Task 3.3 — Pydantic enforcement active — bad tier test

**Claude Code prompt:**

```
Write a test function in api/tests/test_schema_enforcement.py:

test_pydantic_rejects_lowercase_tier():
  1. Directly insert a row into customer_risk_profiles:
     INSERT INTO customer_risk_profiles VALUES ('TEST-BAD', 'low', '{"test factor"}')
     Use a raw psycopg2 connection to bypass the CHECK constraint
     (this requires temporarily disabling the constraint or using a direct insert
     that explicitly bypasses it — use ALTER TABLE ... DISABLE TRIGGER ALL for the
     insert, then re-enable).
  2. Call GET /customers/TEST-BAD with a valid API key.
  3. Assert HTTP 500 (Pydantic rejects 'low' through the response_model chain).
  4. Clean up: DELETE FROM customer_risk_profiles WHERE customer_id = 'TEST-BAD'.

Note: This test confirms that response_model=CustomerResponse on the route decorator
is wired correctly — Pydantic validation fires on the response, not just on input.
```

**Test cases:**

- T3.3.1: `GET /customers/TEST-BAD` with `risk_tier='low'` in DB returns 500, not 200 with `"low"`.

**Verification command:**

```bash
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
ALTER TABLE customer_risk_profiles DISABLE TRIGGER ALL;
INSERT INTO customer_risk_profiles VALUES ('TEST-BAD', 'low', '{\"test factor\"}');
ALTER TABLE customer_risk_profiles ENABLE TRIGGER ALL;
"
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" http://localhost:8000/customers/TEST-BAD
# Expected: 500
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "DELETE FROM customer_risk_profiles WHERE customer_id = 'TEST-BAD';"
```

**Invariants touched:** INV-08 (response_model wiring confirmation)

---

### Session 3 Gate

**Sign-off checklist:**
- [ ] All three injection strings — row count 9 confirmed post-call
- [ ] CUST-007 tier unchanged after UPDATE injection attempt
- [ ] DB-down returns `{"detail": "Internal server error"}` — verified
- [ ] DB-down response contains none of the five prohibited strings — verified
- [ ] Pydantic rejects `'low'` tier — 500 confirmed

---

## Session 4 — UI Layer

**Goal:** Implement `static/index.html` such that all API response values are
rendered verbatim via `textContent`. All error paths display raw `detail` strings
and HTTP status codes.

---

### Task 4.1 — UI implementation

**Claude Code prompt:**

```
Write static/index.html for the Customer Risk API.

Functional requirements:
1. Two input fields: customer ID (text input) and API key (password input).
2. One submit button labeled "Look up".
3. A results area that displays the response.

On successful lookup (HTTP 200):
- Display customer_id, risk_tier, and each element of risk_factors.
- All values must be assigned via element.textContent — not innerHTML, not
  innerText, not setAttribute.
- No mapping of tier values (do not map "HIGH" to "High Risk" or any other string).
- No conditional CSS classes or visual states keyed on tier value.
- No transformation of risk_factors strings.

On error (any non-200 response):
- Display the HTTP status code from the response.
- Display the detail field from the response JSON body exactly as returned.
- Use element.textContent for all DOM assignments.
- Do not substitute user-friendly alternative strings for the raw detail value.

Technical constraints:
- Vanilla JavaScript only. No frameworks, no npm, no CDN imports.
- fetch() for API calls with method: 'GET' and headers: {'X-API-Key': apiKeyValue}.
- The results area must be empty/cleared before each new lookup.
- No hard-coded API key in the HTML or JavaScript.
```

**Test cases:**

- T4.1.1: `GET /` returns 200 with HTML content-type.
- T4.1.2: Looking up `CUST-001` displays the exact `risk_tier` string from the API response.
- T4.1.3: Looking up `CUST-001` displays each risk factor string verbatim.
- T4.1.4: Looking up `CUST-NONE` displays the status code `404` and the string `Customer not found`.
- T4.1.5: Looking up with wrong API key displays status code `401`.
- T4.1.6: Static review — no `innerHTML` assignments for API-sourced values.
- T4.1.7: Static review — no switch/object map keyed on `risk_tier` values.
- T4.1.8: Static review — no hard-coded API key string in the file.

**Verification command:**

```bash
# Manual browser test for T4.1.2, T4.1.3, T4.1.4, T4.1.5
# Static review:
grep "innerHTML" static/index.html && echo "FAIL — innerHTML used" || echo "PASS — no innerHTML"
grep -E "switch.*risk_tier|HIGH.*:.*Risk|MEDIUM.*:.*Risk|LOW.*:.*Risk" static/index.html && echo "FAIL — tier mapping present" || echo "PASS — no tier mapping"
grep -E "API_KEY|api_key\s*=" static/index.html | grep -v "apiKey\|X-API-Key\|input" && echo "WARN — possible hardcoded key" || echo "PASS"
```

**Invariants touched:** INV-16

---

### Task 4.2 — UI error path verification

**Claude Code prompt:**

```
Extend the UI test coverage in a manual test script at api/tests/test_ui_manual.md.

Document the following manual test steps with expected outcomes:

1. Load the UI at http://localhost:8000/
   Expected: Page loads, two input fields and a button are visible.

2. Enter CUST-001 and the correct API key, click Look up.
   Expected: The exact risk_tier string from the API response is visible (e.g. "HIGH").
   The risk_factors list is visible with exact strings.

3. Enter CUST-NONE and the correct API key, click Look up.
   Expected: Status code 404 is visible. The string "Customer not found" is visible verbatim.

4. Enter CUST-001 and a wrong API key, click Look up.
   Expected: Status code 401 is visible. The string "Unauthorized" is visible verbatim.

5. Enter CUST-001 and the correct API key, stop the db container, click Look up.
   Expected: Status code 500 is visible. The string "Internal server error" is visible verbatim.
   Restart the db container after this step.

For each step, note: PASS or FAIL, and the exact text observed in the results area.
```

**Test cases:** (manual confirmation)

- T4.2.1–T4.2.5: Each step above passes.

**Verification command:** Manual browser execution. Engineer signs off on each step.

**Invariants touched:** INV-16

---

### Session 4 Gate

**Sign-off checklist:**
- [ ] UI renders `risk_tier` verbatim — confirmed for all three tiers
- [ ] UI renders `risk_factors` verbatim — confirmed
- [ ] 404 path: status code and `"Customer not found"` visible
- [ ] 401 path: status code and `"Unauthorized"` visible
- [ ] 500 path (DB down): status code and `"Internal server error"` visible
- [ ] No `innerHTML` for API-sourced values — reviewed
- [ ] No tier mapping logic — reviewed
- [ ] No hard-coded API key — reviewed

---

## Session 5 — Integration and Invariant Sweep

**Goal:** Run a complete end-to-end test pass against all 18 invariants. Close
any open gaps from earlier sessions. Produce the final sign-off checklist.

---

### Task 5.1 — Full seed data round-trip test

**Claude Code prompt:**

```
Write api/tests/test_roundtrip.py for the Customer Risk API.

For each of the 9 seed customers (CUST-001 through CUST-009):
1. Query the database directly with psycopg2 for the row.
2. Call GET /customers/{customer_id} with a valid API key.
3. Assert HTTP 200.
4. Assert response["customer_id"] == db_row["customer_id"] (character-for-character).
5. Assert response["risk_tier"] == db_row["risk_tier"] (character-for-character).
6. Assert response["risk_factors"] == db_row["risk_factors"] (list equality).
7. Assert the response contains exactly three keys: customer_id, risk_tier, risk_factors.

This test covers INV-01 (exact match), INV-02 (all customers retrievable),
INV-07 (exactly three fields).
```

**Test cases:**

- T5.1.1–T5.1.9: All 9 customers return 200 with character-for-character match to DB values.
- T5.1.10: No response contains more than 3 keys.

**Verification command:**

```bash
API_KEY=$API_KEY pytest api/tests/test_roundtrip.py -v
```

**Invariants touched:** INV-01, INV-02, INV-07

---

### Task 5.2 — Authentication edge case sweep

**Claude Code prompt:**

```
Write api/tests/test_auth_sweep.py for the Customer Risk API.

Test functions:

test_no_header_returns_401():
  - GET /customers/CUST-001 with no X-API-Key header
  - Assert 401, not 422
  - Assert response body contains no customer data fields

test_wrong_key_returns_401():
  - GET /customers/CUST-001 with X-API-Key: wrongkeyvalue
  - Assert 401
  - Assert the string "wrongkeyvalue" does not appear in the response body

test_empty_key_returns_401():
  - GET /customers/CUST-001 with X-API-Key: (empty string)
  - Assert 401

test_authorization_header_returns_401_not_422():
  - GET /customers/CUST-001 with Authorization: Bearer <correct_key>
    and no X-API-Key header
  - Assert 401, not 422

test_health_requires_no_auth():
  - GET /health with no API key
  - Assert 200
  - Assert body is exactly {"status": "ok"}
  - Assert body has no additional keys
```

**Test cases:** T5.2.1–T5.2.5 correspond to the five test functions.

**Verification command:**

```bash
API_KEY=$API_KEY pytest api/tests/test_auth_sweep.py -v
```

**Invariants touched:** INV-09, INV-10, INV-11

---

### Task 5.3 — git history check for .env

**Claude Code prompt:**

```
Document the following two verification commands in api/tests/test_git_hygiene.md:

Command 1 (working tree check):
  git ls-files | grep -E '^\.env$'
  Expected output: (nothing — empty)
  If output is non-empty: FAIL — .env is tracked in working tree

Command 2 (full history check):
  git log --all --full-history -- .env
  Expected output: (nothing — empty)
  If output is non-empty: FAIL — .env appears in git history and is recoverable

Both checks are required. Passing command 1 does not imply passing command 2.
A file removed via git rm --cached passes command 1 but fails command 2.

Document the remediation steps if command 2 fails (git filter-branch or BFG).
```

**Test cases:**

- T5.3.1: Working tree check returns empty.
- T5.3.2: History check returns empty.

**Verification command:**

```bash
git ls-files | grep -E '^\.env$' && echo "FAIL" || echo "PASS — .env not tracked"
git log --all --full-history -- .env | head -1 && echo "FAIL — .env in history" || echo "PASS — .env not in history"
```

**Invariants touched:** INV-12

---

### Task 5.4 — Outbound network static review

**Claude Code prompt:**

```
Document a static review checklist in api/tests/test_network_isolation.md:

1. Review requirements.txt — confirm no requests, httpx, aiohttp, or urllib3
   (beyond what psycopg2-binary and uvicorn bring transitively) is present.
   Command: grep -iE "requests|httpx|aiohttp" api/requirements.txt

2. Review all .py files in api/app/ — confirm no import of requests, httpx,
   socket, urllib.request, or any module that makes external network calls.
   Command: grep -rE "import requests|import httpx|import socket|urllib.request" api/app/

3. Review docker-compose.yml — confirm no external network is defined
   (no networks block entries pointing to external: true).
   Command: grep "external" docker-compose.yml

4. Review all configuration files — confirm no external hostnames, URLs, or IPs
   appear outside of the internal service names (db, api).
   Confirm: no api.example.com, no 0.0.0.0 targets other than the bind address.

Document the result of each check as PASS or FAIL.
```

**Test cases:**

- T5.4.1–T5.4.4: All four checks return PASS.

**Verification command:** Commands documented above, run by engineer.

**Invariants touched:** INV-15

---

### Task 5.5 — Final invariant sweep table

**Claude Code prompt:**

```
Produce a final verification table as a markdown file at VERIFICATION.md in the
project root.

The table must have columns: INV ID | Statement (one line) | Test/Check reference |
Status (PASS / FAIL / OPEN)

Populate one row per invariant (INV-01 through INV-18) using the test and check
references from Execution_Plan.md.

Leave the Status column blank — the engineer fills this in during the final review
session. Do not pre-populate Status with PASS.
```

**Test cases:**

- T5.5.1: VERIFICATION.md exists with 18 rows.
- T5.5.2: Status column is blank for all rows (not pre-populated).

**Verification command:**

```bash
wc -l VERIFICATION.md  # Should be at least 22 lines (header + separator + 18 rows + 1 title)
grep "PASS\|FAIL" VERIFICATION.md | grep -v "header\|column" && echo "WARN — status pre-populated" || echo "PASS — status column blank"
```

**Invariants touched:** All (sweep artifact)

---

### Session 5 Gate — Final Sign-off

**This is the project completion gate. The engineer signs off on each item.**

**Functional completeness:**
- [ ] All 9 seed customers retrievable — T5.1 test suite passes
- [ ] Round-trip values match DB character-for-character — T5.1 confirmed
- [ ] `/health` unauthenticated, exact body — T5.2 confirmed
- [ ] All auth edge cases pass — T5.2 confirmed

**Security:**
- [ ] Three injection strings — no DB change — T3.1 confirmed
- [ ] DB-down returns generic 500 — T3.2 confirmed
- [ ] API key never in response body — T5.2 confirmed
- [ ] `.env` not in working tree — T5.3 command 1 confirmed
- [ ] `.env` not in git history — T5.3 command 2 confirmed
- [ ] No outbound network calls — T5.4 static review confirmed

**Schema correctness:**
- [ ] `extra='forbid'` on both Pydantic models — code review confirmed
- [ ] `response_model=CustomerResponse` on route decorator — code review confirmed
- [ ] `-> CustomerResponse` return type on handler — code review confirmed
- [ ] Pydantic rejects lowercase tier — T3.3 confirmed

**Startup:**
- [ ] Empty `API_KEY` → non-zero exit, no port binding — T2.5.1 confirmed
- [ ] Short `API_KEY` → non-zero exit — T2.5.2 confirmed

**UI:**
- [ ] All values rendered via `textContent` — code review confirmed
- [ ] No tier mapping logic — code review confirmed
- [ ] All error paths show raw `detail` and status code — T4.2 manual confirmed

**Route completeness:**
- [ ] Exactly three routes — route enumeration test passes
- [ ] No triggers or functions in init.sql — static review confirmed

**VERIFICATION.md:** [ ] All 18 rows present; engineer has signed off status for each.

---

## Appendix — Invariant-to-Task Cross-Reference

| Invariant | Primary task(s) | Verification type |
|---|---|---|
| INV-01 | T1.3, T5.1 | Automated + DB direct query |
| INV-02 | T5.1 | Automated |
| INV-03 | T2.4 | Automated + static review |
| INV-04 | T2.4 | Automated + static review |
| INV-05 | T2.3, T3.1 | Automated (confirmatory) + static review |
| INV-06 | T1.3 | Static review of init.sql |
| INV-07 | T2.1, T5.1 | Automated + static review |
| INV-08 | T2.4, T3.3 | Automated + static review |
| INV-09 | T2.2, T5.2 | Automated |
| INV-10 | T2.4, T5.2 | Automated + static review |
| INV-11 | T2.2, T5.2 | Automated |
| INV-12 | T1.1, T5.3 | Git commands (both checks) |
| INV-13 | T2.3, T3.2 | Automated + manual |
| INV-14 | T2.3, T3.2 | Automated + static review |
| INV-15 | T1.2, T5.4 | Static review |
| INV-16 | T4.1, T4.2 | Static review + manual browser |
| INV-17 | T2.6 | Automated (route enumeration) |
| INV-18 | T2.5 | Container startup test |

---

*Customer Risk API · Execution_Plan.md · DataGrokr Engineering · 2026*