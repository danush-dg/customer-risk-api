# EXECUTION_PLAN.md
## Customer Risk API

*Version 1.1 · DataGrokr Engineering · 2026*

---

## How to read this document

Delivery is divided into three sessions in strict dependency order. Each session ends with a gate — a set of verification commands that must all pass before the next session begins. **Claude never declares a gate passed. Only the engineer signs off.**

Each task contains:
- **Prompt** — the exact Claude Code prompt to execute
- **Test cases** — discrete assertions to check before running the verification command
- **Verification command** — the terminal command that confirms the task is done
- **Invariants** — which invariants from `INVARIANTS.md` this task implements or exercises

If a task prompt conflicts with an invariant, the invariant wins. Flag the conflict; never resolve it silently.

---

## Session Overview

| Session | Title | Tasks | Scope | Gate Invariants |
|---|---|---|---|---|
| S1 | Infrastructure & Data | 5 | Docker Compose, Postgres schema, seed data, healthcheck | INV-01, 02, 05, 06, 12 |
| S2 | API Service | 6 | FastAPI app, auth, routes, schemas, error handling, startup validation | INV-03–05, 07–11, 13, 14, 17, 18 |
| S3 | UI & System Validation | 4 | HTML/JS UI, static serving, end-to-end invariant sweep | INV-01–18 (full sweep) |

---

## Session 1 — Infrastructure & Data

Session 1 produces a running Docker Compose stack: a healthy Postgres database pre-seeded with representative customer records, and a verified API container placeholder that can reach the database. No application logic is written in this session. The gate is that `docker compose up` starts cleanly and the database contains correct seed data.

---

### Task 1.1 — Repository Scaffold & .env Setup

**Invariants:** INV-12
**Depends on:** Nothing — first task

#### Prompt

```
Create the repository scaffold for the Customer Risk API project. Produce the
following file tree and nothing else — no application code yet:

  customer-risk-api/
    docker-compose.yml       (stub — two services: db, api)
    .env.example             (API_KEY=, POSTGRES_DB=, POSTGRES_USER=, POSTGRES_PASSWORD=)
    .gitignore               (must include .env on its own line)
    db/
      init.sql               (empty file)
    api/
      Dockerfile             (FROM python:3.11-slim stub)
      requirements.txt       (empty)
      app/
        __init__.py
        main.py              (empty)
        router.py            (empty)
        auth.py              (empty)
        db.py                (empty)
        schemas.py           (empty)
    ui/
      index.html             (empty)

Rules:
- .gitignore must contain the line: .env
- .env.example must not contain any real values — only placeholder text.
- Do not create a .env file. The engineer will create it manually.
- Do not write any Python, SQL, or JavaScript code in this task.
```

#### Test Cases

- **TC-1.1-A:** `ls customer-risk-api/` shows all expected top-level entries.
- **TC-1.1-B:** `cat .gitignore | grep -E '^\.env$'` returns `.env`.
- **TC-1.1-C:** `ls customer-risk-api/` does NOT show a `.env` file.
- **TC-1.1-D:** `cat .env.example` contains `API_KEY=`, `POSTGRES_DB=`, `POSTGRES_USER=`, `POSTGRES_PASSWORD=` — no real values.

#### Verification Command

```bash
# .env must not be tracked
git ls-files | grep -E '^\.env$'
# → must return nothing

# .env must be in .gitignore
cat .gitignore | grep -E '^\.env$'
# → must return: .env

# app module files must exist
ls api/app/
# → must list: __init__.py  auth.py  db.py  main.py  router.py  schemas.py
```

---

### Task 1.2 — Postgres Schema (`db/init.sql`)

**Invariants:** INV-01, INV-02, INV-06, INV-08
**Depends on:** Task 1.1

#### Prompt

```
Write db/init.sql to define and seed the customer_risk_profiles table.

Schema requirements:
- Table name: customer_risk_profiles
- Columns: customer_id VARCHAR(50) PRIMARY KEY,
           risk_tier  VARCHAR(10) NOT NULL,
           risk_factors TEXT[] NOT NULL
- CHECK constraint on risk_tier: CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))
- No triggers. No stored procedures. No functions. No views.

Seed data requirements (minimum 9 rows, 3 per tier):
- customer_id format: CUST-NNN (e.g. CUST-001)
- LOW tier    (3 rows): simple, benign risk_factors arrays
- MEDIUM tier (3 rows): mixed-signal risk_factors arrays
- HIGH tier   (3 rows): serious risk_factors arrays
- At least one row across any tier must have an empty risk_factors array
  (i.e. risk_factors = '{}') to enable INV-07 empty-list verification.
  Record which customer_id has the empty array — it will be referenced in
  the Task 2.6 gate.

Constraints:
- risk_factors must be a native Postgres TEXT[] array literal, not JSON.
- All risk_tier values must be exactly LOW, MEDIUM, or HIGH — uppercase.
- No INSERT may violate the CHECK constraint.
- The file must be valid SQL with no syntax errors.
```

#### Test Cases

- **TC-1.2-A:** File contains `CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))` — grep confirms.
- **TC-1.2-B:** No `CREATE TRIGGER` or `CREATE FUNCTION` statement appears in `init.sql`.
- **TC-1.2-C:** Exactly 9 rows are inserted (3 per tier).
- **TC-1.2-D:** All `customer_id` values match format `CUST-NNN`.
- **TC-1.2-E:** All `risk_tier` values are exactly `LOW`, `MEDIUM`, or `HIGH`.

#### Verification Command

```bash
# Static: no triggers or functions
grep -i 'CREATE TRIGGER\|CREATE FUNCTION' db/init.sql
# → must return nothing

# Static: CHECK constraint present
grep 'CHECK' db/init.sql
# → must show the risk_tier CHECK constraint

# Runtime: row count after stack start
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT COUNT(*) FROM customer_risk_profiles;"
# → 9

# Runtime: all three tiers present
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT DISTINCT risk_tier FROM customer_risk_profiles ORDER BY risk_tier;"
# → HIGH / LOW / MEDIUM

# Runtime: CHECK constraint is active (must FAIL)
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "INSERT INTO customer_risk_profiles VALUES ('TEST-BAD','low','{}');"
# → ERROR: new row for relation "customer_risk_profiles" violates check constraint
```

---

### Task 1.3 — Docker Compose & Healthcheck Configuration

**Invariants:** INV-12 (no secrets in Compose), INV-15 (no external networks)
**Depends on:** Tasks 1.1, 1.2

#### Prompt

```
Write docker-compose.yml for the Customer Risk API system.

Service: db
- Image: postgres:15
- Environment: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD — all read from
  .env via ${VAR} substitution. No hardcoded values.
- Volume mount: ./db/init.sql → /docker-entrypoint-initdb.d/init.sql
- Healthcheck: pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB},
  interval 5s, timeout 3s, retries 10, start_period 10s

Service: api
- Build: ./api
- Ports: "8000:8000"
- Environment: API_KEY, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
  POSTGRES_HOST=db — all read from .env via ${VAR} substitution. No hardcoded values.
- depends_on: db, condition: service_healthy
- Volume mount (UI): ./ui/index.html → /app/static/index.html

Network:
- Define one internal network (e.g. risk-net) with no external: true.
- Both services must be on this network.
- No external DNS names, no internet-facing configurations.

Rules:
- No secrets, passwords, or API keys may be hardcoded in this file.
- Do not add any third service.
```

#### Test Cases

- **TC-1.3-A:** `grep -i 'password\|api_key\|secret' docker-compose.yml | grep -v '\${'` → must return nothing.
- **TC-1.3-B:** `grep 'external: true' docker-compose.yml` → must return nothing.
- **TC-1.3-C:** File defines exactly two services: `db` and `api`.
- **TC-1.3-D:** `api` depends_on `db` with `condition: service_healthy`.
- **TC-1.3-E:** `db` healthcheck uses `pg_isready` with `retries: 10`.

#### Verification Command

```bash
# Valid Compose YAML
docker compose config --quiet
# → must exit 0

# db reaches healthy state
docker compose up -d db
docker compose ps
# → db shows (healthy)
```

---

### Task 1.4 — API Dockerfile & `requirements.txt`

**Invariants:** INV-15 (no external calls introduced by dependencies)
**Depends on:** Task 1.1

#### Prompt

```
Write api/Dockerfile and api/requirements.txt for the FastAPI service.

Dockerfile requirements:
- Base image: python:3.11-slim
- WORKDIR /app
- Copy requirements.txt and install dependencies
- Copy the app/ directory
- Create /app/static/ directory
- Expose port 8000
- CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000

requirements.txt must contain exactly:
  fastapi==0.111.0
  uvicorn==0.29.0
  psycopg2-binary==2.9.9
  pydantic==2.7.1

No other packages. No requests, httpx, or any HTTP client library.
No telemetry packages.
```

#### Test Cases

- **TC-1.4-A:** `grep -i 'requests\|httpx\|aiohttp\|urllib' api/requirements.txt` → nothing.
- **TC-1.4-B:** `requirements.txt` contains exactly 4 dependency lines.
- **TC-1.4-C:** Dockerfile CMD uses `uvicorn` with `--host 0.0.0.0 --port 8000`.
- **TC-1.4-D:** `docker compose build api` exits 0.

#### Verification Command

```bash
docker compose build api
# → must exit 0

grep -c '.' api/requirements.txt
# → 4
```

---

### Task 1.5 — Session 1 Gate: Stack Start & Data Verification ★

**Invariants:** INV-01, INV-02, INV-06
**Depends on:** Tasks 1.1–1.4 complete

> **Gate task.** Run every command below and record the result. Do not begin Session 2 until all pass. Engineer sign-off required.

#### Verification Commands

```bash
# 1. Start the full stack
docker compose up -d

# 2. Confirm both services
docker compose ps
# → both running; db status = healthy

# 3. Seed data present and correct
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT customer_id, risk_tier FROM customer_risk_profiles ORDER BY risk_tier;"
# → 9 rows, all three tiers

# 4. Schema shows CHECK constraint
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "\d customer_risk_profiles"
# → CHECK constraint visible on risk_tier

# 5. Static: no triggers or functions in init.sql
grep -i 'CREATE TRIGGER\|CREATE FUNCTION' db/init.sql
# → nothing

# 6. API container logs (stub — connection errors expected, no crash)
docker compose logs api
```

#### Gate Criteria

- Both containers running after `docker compose up -d`.
- `db` service is healthy (not just running).
- `SELECT` returns exactly 9 rows covering all three tiers.
- `\d` output shows the `CHECK` constraint on `risk_tier`.
- No `CREATE TRIGGER` or `CREATE FUNCTION` in `init.sql` (static).
- **Engineer signs off before Session 2 begins.**

---

## Session 2 — API Service

Session 2 produces a fully working, hardened FastAPI service. By the end of this session all invariants except INV-16 (UI) are verifiable. Tasks build in strict dependency order: schemas → database access → authentication → routes → startup validation → gate.

---

### Task 2.1 — Pydantic Schemas (`schemas.py`)

**Invariants:** INV-07, INV-08, INV-10
**Depends on:** Task 1.5 gate passed

#### Prompt

```
Write api/app/schemas.py containing exactly two Pydantic v2 models.

Model 1 — CustomerResponse:
  Fields: customer_id: str, risk_tier: str, risk_factors: list[str]
  Config: model_config = ConfigDict(extra="forbid")
  No default values. All fields required.

Model 2 — HealthResponse:
  Fields: status: str
  Config: model_config = ConfigDict(extra="forbid")

Imports required:
  from pydantic import BaseModel, ConfigDict

Rules:
- extra="forbid" — not extra="ignore".
- No validators, no field_validators, no computed fields.
- No other models, helpers, or code in this file.
```

#### Test Cases

- **TC-2.1-A:** `CustomerResponse(customer_id='X', risk_tier='HIGH', risk_factors=['a'])` — instantiates without error.
- **TC-2.1-B:** `CustomerResponse(customer_id='X', risk_tier='HIGH', risk_factors=['a'], extra_field='y')` — raises `ValidationError`.
- **TC-2.1-C:** `HealthResponse(status='ok')` — instantiates without error.
- **TC-2.1-D:** `HealthResponse(status='ok', version='1')` — raises `ValidationError`.
- **TC-2.1-E:** `CustomerResponse(customer_id='X', risk_tier='HIGH')` (missing `risk_factors`) — raises `ValidationError`.

#### Verification Command

```bash
python3 -c "
from api.app.schemas import CustomerResponse, HealthResponse
from pydantic import ValidationError

assert CustomerResponse(customer_id='A', risk_tier='HIGH', risk_factors=[]).risk_factors == []

try:
    CustomerResponse(customer_id='A', risk_tier='HIGH', risk_factors=[], bad='x')
    assert False, 'should have raised'
except ValidationError:
    pass

try:
    HealthResponse(status='ok', extra='x')
    assert False, 'should have raised'
except ValidationError:
    pass

print('PASS')
"
```

---

### Task 2.2 — Database Access Layer (`db.py`)

**Invariants:** INV-01, INV-02, INV-03, INV-04, INV-05, INV-13, INV-14
**Depends on:** Task 2.1

#### Prompt

```
Write api/app/db.py with a single public function: get_customer(customer_id: str).

Function behaviour:
- Open a psycopg2 connection using environment variables:
  POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD.
- Open the cursor using RealDictCursor so that fetchone() returns a dict
  keyed by column name, not a positional tuple:
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)
  This is required. Do not use the default cursor and construct the dict
  manually from positional indices — column order in init.sql must not be
  a runtime dependency.
- Execute the following query using a parameterised placeholder — %s with a
  values tuple, never string formatting or concatenation:
    SELECT customer_id, risk_tier, risk_factors
    FROM customer_risk_profiles
    WHERE customer_id = %s
- If no row is returned:
    raise HTTPException(status_code=404, detail="Customer not found")
  The detail must be a string literal — not an f-string and not any expression
  referencing customer_id.
- If a row is returned: return dict(row) — the RealDictCursor row cast to a
  plain dict. The keys will be customer_id, risk_tier, risk_factors matching
  the SELECT column list exactly.
- Close the connection in a finally block regardless of outcome.

Exception handling — every function must have both clauses in this order:
  except psycopg2.Error:
      raise HTTPException(status_code=500, detail="Internal server error")
  except Exception:
      raise HTTPException(status_code=500, detail="Internal server error")

The caught exception variable must NOT appear anywhere in the raise statement —
no str(e), no e.args, no f-strings referencing e.

No ORM. No connection pool. No async.
```

#### Test Cases

- **TC-2.2-A:** `grep 'cursor.execute' db.py` shows `%s` and a tuple — not an f-string or `%` formatting.
- **TC-2.2-B:** Both `except psycopg2.Error` and bare `except Exception` clauses present with static `"Internal server error"` literal.
- **TC-2.2-C:** `grep -n 'str(e)\|e\.args\|e\.message' api/app/db.py` → nothing.
- **TC-2.2-D:** The 404 `detail` is the string literal `"Customer not found"` — not an f-string.
- **TC-2.2-E (runtime):** Call with `CUST-001` → returns dict with keys `customer_id`, `risk_tier`, `risk_factors`.
- **TC-2.2-F (runtime):** Call with `CUST-999` (absent) → raises `HTTPException` 404.
- **TC-2.2-G (injection):** Call with `'; DROP TABLE customer_risk_profiles; --` → HTTP 404, response body is exactly `{"detail": "Customer not found"}`, the submitted string does not appear anywhere in the response body, and table row count is unchanged at 9.
- **TC-2.2-H (injection):** Call with `1 OR 1=1` → HTTP 404, response body is exactly `{"detail": "Customer not found"}`, submitted string not in body, row count unchanged.
- **TC-2.2-I (injection):** Call with `CUST-001'; UPDATE customer_risk_profiles SET risk_tier='LOW' WHERE '1'='1` → HTTP 404, response body is exactly `{"detail": "Customer not found"}`, submitted string not in body, row count unchanged and CUST-007 (HIGH tier) still returns `HIGH` after the call.

#### Verification Command

```bash
# Static: no f-strings in SQL or exception clauses
grep -n "f\"\\|f'" api/app/db.py
# → nothing

# Static: no exception variable leak
grep -n 'str(e)\|e\.args\|e\.message' api/app/db.py
# → nothing

# Injection test — all three INV-05 strings (full stack running)
# Each must: return 404, body exactly {"detail":"Customer not found"},
# submitted value not reflected, row count unchanged after all three.

BODY=$(curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/%27%3B%20DROP%20TABLE%20customer_risk_profiles%3B%20--")
echo "$BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d == {'detail':'Customer not found'}, f'FAIL: {d}'
assert 'DROP' not in json.dumps(d), 'FAIL: submitted value reflected'
print('injection-1 PASS')
"

BODY=$(curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/1%20OR%201%3D1")
echo "$BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d == {'detail':'Customer not found'}, f'FAIL: {d}'
print('injection-2 PASS')
"

BODY=$(curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/CUST-001%27%3B%20UPDATE%20customer_risk_profiles%20SET%20risk_tier%3D%27LOW%27%20WHERE%20%271%27%3D%271")
echo "$BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d == {'detail':'Customer not found'}, f'FAIL: {d}'
print('injection-3 PASS')
"

# Row count must still be 9
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT COUNT(*) FROM customer_risk_profiles;"
# → 9

# HIGH-tier row must be unchanged (injection-3 targeted it)
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-007 | \
  python3 -c "import json,sys; d=json.load(sys.stdin); assert d['risk_tier']=='HIGH'; print('tier intact PASS')"
```

---

### Task 2.3 — Authentication Dependency (`auth.py`)

**Invariants:** INV-09, INV-11
**Depends on:** Task 2.1

#### Prompt

```
Write api/app/auth.py with a single FastAPI dependency function: verify_api_key.

Function signature:
  def verify_api_key(
      api_key: str = Header(default=None, alias="X-API-Key")
  ) -> None:

Behaviour:
- Read the expected key from os.environ["API_KEY"].
- If api_key is None or api_key != expected_key:
      raise HTTPException(status_code=401, detail="Unauthorized")
  The detail must be the string literal "Unauthorized" — not an f-string and
  not any expression containing api_key.
- If the key matches: return None.

The function must use Header(default=None) — not a required Header — so that
a missing X-API-Key header arrives as None and triggers the 401 explicitly,
rather than causing FastAPI to return 422 before the function runs.

No logging of the submitted key value.
No other functions, helpers, or code in this file.
```

#### Test Cases

- **TC-2.3-A:** Missing `X-API-Key` header → 401 (not 422).
- **TC-2.3-B:** Wrong key value → 401.
- **TC-2.3-C:** Empty string as key value → 401.
- **TC-2.3-D:** Correct key → function returns `None` (no exception).
- **TC-2.3-E:** 401 response body does not contain the submitted key string.
- **TC-2.3-F:** `grep "f\"\\|f'" auth.py` → nothing in detail strings.

#### Verification Command

```bash
# Missing header → 401 not 422
curl -s -o /dev/null -w '%{http_code}' \
  http://localhost:8000/customers/CUST-001
# → 401

# Wrong key → 401
curl -s -o /dev/null -w '%{http_code}' \
  -H "X-API-Key: wrongkey" http://localhost:8000/customers/CUST-001
# → 401

# Wrong key must not appear in response body
curl -s -H "X-API-Key: wrongkey" \
  http://localhost:8000/customers/CUST-001 | grep 'wrongkey'
# → nothing

# Authorization Bearer (wrong header name) → 401 not 422
curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer $API_KEY" http://localhost:8000/customers/CUST-001
# → 401
```

---

### Task 2.4 — Route Definitions (`router.py`)

**Invariants:** INV-03, INV-07, INV-08, INV-09, INV-10, INV-17
**Depends on:** Tasks 2.1, 2.2, 2.3

#### Prompt

```
Write api/app/router.py with exactly two routes on an APIRouter instance.

Route 1 — Health:
  @router.get("/health", response_model=HealthResponse)
  def health_check() -> HealthResponse:
      return HealthResponse(status="ok")
  No auth dependency. No additional logic.

Route 2 — Customer lookup:
  @router.get("/customers/{customer_id}", response_model=CustomerResponse)
  def get_customer(
      customer_id: str,
      _: None = Depends(verify_api_key)
  ) -> CustomerResponse:
      return CustomerResponse(**get_customer(customer_id))

  Import the db function as:
    from app.db import get_customer as get_customer_from_db
  and call it as get_customer_from_db(customer_id) to avoid a name collision
  with the route handler. Or name the route handler get_customer_by_id and
  import get_customer directly. Either convention is acceptable — what is not
  acceptable is importing a name that does not exist in app.db.

  The verify_api_key dependency must be injected via Depends() as a function
  argument — not via middleware and not as a manual call inside the handler.

Rules:
- response_model must be set on both route decorators.
- Return type annotation must be the Pydantic model on both handlers.
- No other routes. No POST, PUT, DELETE, or PATCH handlers.
- No logic beyond calling the db function and returning the model.
- The import of the db lookup function must use the exact name defined in
  app.db (get_customer). Any alias used in router.py must be declared
  explicitly in the import statement.
```

#### Test Cases

- **TC-2.4-A:** `grep 'response_model' router.py` → shows both `CustomerResponse` and `HealthResponse`.
- **TC-2.4-B:** `grep 'Depends(verify_api_key)' router.py` → exactly one match.
- **TC-2.4-C:** No `POST`/`PUT`/`DELETE`/`PATCH` decorators in the file.
- **TC-2.4-G:** `grep '\-> CustomerResponse' api/app/router.py` → exactly one match (return type annotation on the customer handler).
- **TC-2.4-H:** `grep '\-> HealthResponse' api/app/router.py` → exactly one match (return type annotation on the health handler).
- **TC-2.4-D (runtime):** `GET /health` → 200 `{"status": "ok"}`.
- **TC-2.4-E (runtime):** `GET /customers/CUST-001` with valid key → 200 with exactly `customer_id`, `risk_tier`, `risk_factors`.
- **TC-2.4-F (runtime):** `GET /customers/CUST-999` with valid key → 404 `{"detail": "Customer not found"}`.

#### Verification Command

```bash
# Static: return type annotations present on both handlers
grep '-> CustomerResponse' api/app/router.py
# → exactly one match

grep '-> HealthResponse' api/app/router.py
# → exactly one match

# Static: response_model on both decorators
grep 'response_model' api/app/router.py
# → two matches (CustomerResponse and HealthResponse)

# Router-level route check (main.py not yet written — use router directly)
python3 -c "
from api.app.router import router
paths = {r.path for r in router.routes}
assert '/health' in paths, f'missing /health: {paths}'
assert '/customers/{customer_id}' in paths, f'missing customer route: {paths}'
assert len([r for r in router.routes if hasattr(r, 'methods') and
            any(m in {'POST','PUT','DELETE','PATCH'} for m in (r.methods or {}))]) == 0, \
    'write methods found on router'
print('PASS', paths)
"

# Health endpoint (runtime — stack must be up from Task 1.5)
curl -s http://localhost:8000/health | python3 -m json.tool
# → {"status": "ok"} — exactly, no other fields

# Customer lookup — field set
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001 | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
assert set(d.keys()) == {'customer_id', 'risk_tier', 'risk_factors'}, f'unexpected keys: {d.keys()}'
print('PASS')
"
```

> **Note — full application route enumeration** (confirming `GET /` is present alongside router routes) requires `main.py` to exist. That check is in Task 2.5 where `main.py` is written.

---

### Task 2.5 — Application Entry Point & Startup Validation (`main.py`)

**Invariants:** INV-17, INV-18
**Depends on:** Tasks 2.3, 2.4

#### Prompt

```
Write api/app/main.py as the application entry point.

Structure (in this order):
1. Imports: FastAPI, StaticFiles, FileResponse, os, sys, router from router.py.

2. Startup validation block — module-level code, executes before app is created:
     api_key = os.environ.get("API_KEY", "")
     if not api_key:
         print("FATAL: API_KEY environment variable is not set", flush=True)
         sys.exit(1)
     if len(api_key) < 16:
         print("FATAL: API_KEY must be at least 16 characters", flush=True)
         sys.exit(1)

3. Create app:
     app = FastAPI()

4. Mount static files:
     app.mount("/static", StaticFiles(directory="/app/static"), name="static")

5. Root route:
     @app.get("/")
     def serve_ui():
         return FileResponse("/app/static/index.html")

6. Include router:
     app.include_router(router)

The validation block (step 2) is module-level code, not inside a startup event
or lifespan function. sys.exit(1) must be called before uvicorn binds to any port.

Do not call uvicorn.run() from within this file — uvicorn is called from the
Dockerfile CMD.
```

#### Test Cases

- **TC-2.5-A:** Container started with `API_KEY=` (empty) → exits non-zero, port 8000 not bound.
- **TC-2.5-B:** Container started with `API_KEY=tooshort` (< 16 chars) → exits non-zero, port 8000 not bound.
- **TC-2.5-C:** Container started with valid 16+ character key → starts normally.
- **TC-2.5-D:** `grep 'sys.exit(1)' main.py` → exactly two matches.
- **TC-2.5-F:** The two `sys.exit(1)` lines have lower line numbers than the `app = FastAPI()` line — validation executes before the application object is created, confirming it cannot be deferred to a startup event or lifespan handler. `grep -n 'sys.exit\|app = FastAPI' api/app/main.py` → both `sys.exit` line numbers are less than the `app = FastAPI()` line number.
- **TC-2.5-E:** Route enumeration (full app) returns exactly `{/, /health, /customers/{customer_id}}` plus FastAPI framework routes.

#### Verification Command

```bash
# Empty key → non-zero exit
docker compose run --rm -e API_KEY= api python -c "import app.main"
echo "Exit: $?"
# → Exit: 1

# Short key → non-zero exit
docker compose run --rm -e API_KEY=tooshort api python -c "import app.main"
echo "Exit: $?"
# → Exit: 1

# Validation block must precede app = FastAPI() — line numbers confirm ordering
grep -n 'sys.exit\|app = FastAPI' api/app/main.py
# → the two sys.exit lines must have LOWER line numbers than app = FastAPI()
# Example of compliant output:
#   5:    sys.exit(1)
#   8:    sys.exit(1)
#   11: app = FastAPI()
# A lifespan/startup-event implementation would show sys.exit AFTER app = FastAPI().

# Valid key → normal start
docker compose up -d
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health
# → 200

# Full route enumeration (main.py now exists)
python3 -c "
from api.app.main import app
paths = {r.path for r in app.routes}
required = {'/', '/health', '/customers/{customer_id}'}
assert required.issubset(paths), f'missing routes: {required - paths}'
print('PASS', paths)
"

# Unknown path → 404
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/nonexistent
# → 404

# Wrong method → 405
curl -s -o /dev/null -w '%{http_code}' \
  -X POST http://localhost:8000/customers/CUST-001
# → 405
```

---

### Task 2.6 — Session 2 Gate: API Invariant Sweep ★

**Invariants:** INV-01–05, 07–11, 13, 14, 17, 18
**Depends on:** Tasks 2.1–2.5 complete, full stack running

> **Gate task.** Execute every check below. Record pass/fail per invariant. Do not begin Session 3 until every check passes. Engineer sign-off required.

#### Authentication sweep (INV-09, INV-11)

```bash
# 1. No header → 401
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/customers/CUST-001
# → 401

# 2. Wrong key → 401, key not in body
curl -s -H "X-API-Key: WRONG" http://localhost:8000/customers/CUST-001
# → body must not contain "WRONG"

# 3. Empty key → 401
curl -s -o /dev/null -w '%{http_code}' \
  -H "X-API-Key: " http://localhost:8000/customers/CUST-001
# → 401

# 4. Wrong header name → 401 not 422
curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer $API_KEY" http://localhost:8000/customers/CUST-001
# → 401
```

#### Data correctness (INV-01, INV-02)

```bash
# 5. For each of the 9 seed IDs: API response must match DB row character-for-character
for ID in CUST-001 CUST-002 CUST-003 CUST-004 CUST-005 CUST-006 CUST-007 CUST-008 CUST-009; do
  curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/$ID | python3 -m json.tool
done
# → 200 for all 9; compare each to direct DB query
```

#### Existence mapping (INV-03, INV-04)

```bash
# 6. Absent ID → exact static body
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-999
# → {"detail": "Customer not found"} — exactly

# 7. Garbage ID → same body, no reflection of input
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/%27%3B%20DROP%20TABLE"
# → {"detail": "Customer not found"} — submitted value must not appear
```

#### Injection / mutability (INV-05)

```bash
# 8. Three injection strings from INV-05 — row count must not change
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/%27%3B+DROP+TABLE+customer_risk_profiles%3B+--"
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/1+OR+1%3D1"
curl -s -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/customers/CUST-001%27%3B+UPDATE+customer_risk_profiles+SET+risk_tier%3D%27LOW%27+WHERE+%271%27%3D%271"

docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT COUNT(*) FROM customer_risk_profiles;"
# → 9
```

#### Response shape (INV-07, INV-08)

```bash
# 9–10. Each tier response has exactly 3 fields; risk_tier is exact uppercase string
for ID in CUST-001 CUST-004 CUST-007; do
  curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/$ID | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
assert set(d.keys()) == {'customer_id','risk_tier','risk_factors'}
assert d['risk_tier'] in {'LOW','MEDIUM','HIGH'}
assert isinstance(d['risk_factors'], list)
print('PASS', d['risk_tier'])
"
done

# 10b. Empty risk_factors must return [] not omit the field (INV-07 explicit case)
# Replace CUST-EMPTY below with whichever customer_id was seeded with risk_factors = '{}'
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-EMPTY | \
python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'risk_factors' in d, 'FAIL: risk_factors field omitted for empty array'
assert d['risk_factors'] == [], f'FAIL: expected [] got {d[\"risk_factors\"]}'
print('empty risk_factors PASS')
"
```

#### Health (INV-10)

```bash
# 11. No auth required; exact body
curl -s http://localhost:8000/health
# → {"status": "ok"} — nothing more
```

#### Error surfaces (INV-13, INV-14)

```bash
# 12. DB down → generic 500
docker compose stop db
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
# → {"detail": "Internal server error"} — no hostname, port, or traceback
docker compose start db
```

#### Startup validation (INV-18)

```bash
# 13. Blank key → container exits, does not serve requests
docker compose run --rm -e API_KEY= api python -c "import app.main"
echo "Exit: $?"
# → Exit: 1
```

#### Route completeness (INV-17)

```bash
# 14. Wrong method → 405
curl -s -o /dev/null -w '%{http_code}' \
  -X POST http://localhost:8000/customers/CUST-001
# → 405

# 15. Unknown path → 404
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/admin
# → 404
```

#### Gate Criteria

- All 15 checks above return the asserted result.
- No psycopg2 exception text visible in any HTTP response body.
- No API key visible in any HTTP response body.
- **Engineer signs off before Session 3 begins.**

---

## Session 3 — UI & System Validation

Session 3 delivers the browser UI, validates all invariants end-to-end, and produces the final system ready for sign-off.

---

### Task 3.1 — Browser UI (`ui/index.html`)

**Invariants:** INV-16
**Depends on:** Task 2.6 gate passed

#### Prompt

```
Write ui/index.html as a single self-contained HTML page.
No external scripts, no CDN, no frontend framework.

Layout — the page must contain:
  - A text input for customer_id  (id="customer-id")
  - A text input for the API key  (id="api-key")
  - A submit button
  - A result display area         (id="result")

On submit, the JavaScript must:
  1. Read both input values.
  2. Call:
       fetch("http://localhost:8000/customers/" + customerId,
             { headers: { "X-API-Key": apiKey } })
  3. Await response.json() regardless of status code.
  4. Display both the HTTP status code and the response body in the result area.

DOM assignment rules — critical:
  - All API-sourced values must use element.textContent — never innerHTML.
  - risk_tier and each risk_factor string must be rendered verbatim — no
    mapping to display labels, no conditional CSS classes based on tier value,
    no transformation of any kind.
  - On non-200: display the HTTP status code and the raw detail value from
    the response body — no substitute user-friendly message.
  - Render risk_factors as a list by creating a <ul> element and appending
    <li> elements, each with textContent set to the factor string.

Styling: minimal inline <style> permitted. No framework. No CDN.
```

#### Test Cases

- **TC-3.1-A:** `grep 'innerHTML' ui/index.html` → must return nothing.
- **TC-3.1-B:** No `switch`, object map, or ternary expression keyed on tier value.
- **TC-3.1-H:** `grep -n 'className\|classList' ui/index.html` → must return nothing inside `<script>` blocks. Conditional CSS classes based on tier value are prohibited by INV-16.
- **TC-3.1-C (runtime):** Query `CUST-001` → displays exact tier string `LOW` and all factor strings verbatim.
- **TC-3.1-D (runtime):** Query a HIGH-tier customer → displays exact string `HIGH`, no CSS class variation.
- **TC-3.1-E (runtime):** Wrong API key → result area displays the numeral `401` AND the raw string `Unauthorized`. Both must be visible — not just one.
- **TC-3.1-F (runtime):** `CUST-999` → result area displays the numeral `404` AND the raw string `Customer not found`. Both must be visible.
- **TC-3.1-G (runtime):** Empty customer ID with valid key → displays 404 detail, no JS error in console.

#### Verification Command

```bash
# No innerHTML anywhere
grep -n 'innerHTML' ui/index.html
# → nothing

# No tier-value display mapping (labels, object maps, ternaries)
grep -n 'HIGH.*High\|MEDIUM.*Medium\|LOW.*Low\|switch\|tierMap\|tierLabel' ui/index.html
# → nothing

# No conditional CSS class assignment based on tier value (INV-16)
grep -n 'className\|classList' ui/index.html
# → nothing

# Browser manual: open http://localhost:8000/
# Query CUST-001 with correct key → "LOW" appears in result, all factor strings appear verbatim
# Enter wrong key → result area shows "401" (numeral) AND "Unauthorized" (raw detail string)
# Enter CUST-999 → result area shows "404" (numeral) AND "Customer not found"
```

---

### Task 3.2 — Static File Serving Verification

**Invariants:** INV-10 (UI served from same stack), INV-17 (`GET /` exists)
**Depends on:** Task 3.1

> Verification task only — no code to write.

#### Verification Commands

```bash
# Restart api to pick up updated index.html from volume mount
docker compose restart api

# Root route returns 200
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/
# → 200

# Page contains expected input elements
curl -s http://localhost:8000/ | grep -c '<input'
# → at least 2

# Static mount must not shadow API routes
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health
# → 200
```

#### Test Cases

- **TC-3.2-A:** `GET /` → 200.
- **TC-3.2-B:** Response body contains the `customer-id` input element.
- **TC-3.2-C:** Response body contains the `api-key` input element.
- **TC-3.2-D:** `GET /health` still returns 200 after static mount (API routes not shadowed).

---

### Task 3.3 — UI Invariant Code Review (INV-16 Static Check)

**Invariants:** INV-16
**Depends on:** Task 3.1

> Static code review task — no code to write or run.

Review `ui/index.html` against each criterion and record pass/fail:

| # | Criterion | Command | Expected |
|---|---|---|---|
| R1 | No `innerHTML` assignments | `grep -n "innerHTML" ui/index.html` | nothing |
| R2 | No tier-value display mapping | `grep -n "HIGH\|MEDIUM\|LOW" ui/index.html` then review each match | only raw assignments and comments |
| R3 | Error path shows raw `detail` from response body | Trace non-200 JS path | `responseJson.detail` assigned via `textContent` |
| R4 | HTTP status code displayed on all paths | Trace JS | `response.status` assigned via `textContent` |
| R5 | `risk_factors` rendered via `textContent` on `<li>` | Read JS loop | `li.textContent = factor` — not `li.innerHTML` |

All five items must pass before Task 3.4.

---

### Task 3.4 — Final System Gate: Full Invariant Sweep ★

**Invariants:** INV-01 through INV-18 — complete coverage
**Depends on:** Tasks 3.1–3.3 complete, full stack running

> **Final gate.** Execute the complete sweep. Engineer signs off each invariant individually. Claude does not declare the gate passed.

| ID | Category | Verification | ✓ |
|---|---|---|---|
| INV-01 | Data correctness | Direct DB query for CUST-001, CUST-004, CUST-007. Compare character-by-character to API response. All must match. | ☐ |
| INV-02 | Data correctness | Call API for all 9 seed IDs. All return 200. No ID present in DB returns 404. | ☐ |
| INV-03 | Existence mapping | `GET /customers/CUST-999` with valid key → 404, body exactly `{"detail": "Customer not found"}`. | ☐ |
| INV-04 | Existence mapping | Call with `CUST-999` and with `; DROP TABLE`. Both → 404, identical body. Code review: `detail` is string literal, not f-string. | ☐ |
| INV-05 | Mutability | Three injection IDs from INV-05. After each: `SELECT COUNT(*) → 9`. Spot-check row values unchanged. | ☐ |
| INV-06 | Mutability | `grep -i 'CREATE TRIGGER\|CREATE FUNCTION' db/init.sql` → nothing. Static review only. | ☐ |
| INV-07 | Response shape | Responses for LOW, MEDIUM, HIGH customers each contain exactly `customer_id`, `risk_tier`, `risk_factors`. No nulls. `risk_factors` is always a list. | ☐ |
| INV-08 | Response shape | `risk_tier` values are exactly `LOW`, `MEDIUM`, `HIGH`. Route decorator has `response_model=CustomerResponse`. Handler has `-> CustomerResponse`. | ☐ |
| INV-09 | Authentication | No header → 401. Wrong key → 401. Empty key → 401. `Authorization: Bearer $KEY` → 401 not 422. No data in any 401 body. | ☐ |
| INV-10 | Authentication | `GET /health` with no key → 200, body exactly `{"status": "ok"}`. No extra fields. | ☐ |
| INV-11 | Credential handling | Wrong key → response body does not contain submitted key string. DB stopped → 500 body does not contain key. | ☐ |
| INV-12 | Credential handling | `git ls-files \| grep -E '^\.env$'` → nothing. `git log --all --full-history -- .env` → nothing. `.env.example` present. | ☐ |
| INV-13 | Error surfaces | Stop `db` container. Valid-key request → 500, body exactly `{"detail": "Internal server error"}`. No hostname, port, or traceback. | ☐ |
| INV-14 | Error surfaces | Same as INV-13. Code review: both `except psycopg2.Error` and bare `except Exception` in every `db.py` function. No exception variable in `raise`. | ☐ |
| INV-15 | Operational isolation | `grep -r 'requests\|httpx\|urllib.request' api/app/` → nothing. `docker-compose.yml` has no `external: true`. No external DNS in any config file. | ☐ |
| INV-16 | UI fidelity | `grep -n 'innerHTML' ui/index.html` → nothing. Browser: LOW/MEDIUM/HIGH queries show exact tier strings. 401 shows raw `detail`. | ☐ |
| INV-17 | Route completeness | Route enumeration returns exactly `{/, /health, /customers/{customer_id}}` plus framework routes. `POST /customers/CUST-001` → 405. `GET /admin` → 404. | ☐ |
| INV-18 | Startup validation | `API_KEY=` → container exits non-zero. `API_KEY=tooshort` → container exits non-zero. Valid 16-char key → normal start. | ☐ |

#### Final Gate Criteria

- All 18 rows above checked off by the engineer.
- `docker compose up` starts the full stack from scratch with no manual steps beyond providing `.env`.
- Browser UI accessible at `http://localhost:8000/`.
- **Engineer sign-off recorded. Claude does not declare this gate passed.**

---

## Invariant-to-Task Traceability Matrix

| Invariant | Implemented in | Verified in |
|---|---|---|
| INV-01 | Task 1.2 | Tasks 1.5 ★, 2.6 ★, 3.4 ★ |
| INV-02 | Task 1.2 | Tasks 1.5 ★, 2.6 ★, 3.4 ★ |
| INV-03 | Tasks 2.2, 2.4 | Tasks 2.6 ★, 3.4 ★ |
| INV-04 | Task 2.2 | Tasks 2.6 ★, 3.4 ★ |
| INV-05 | Task 2.2 | Tasks 2.6 ★, 3.4 ★ |
| INV-06 | Task 1.2 (static — absence) | Tasks 1.5 ★, 3.4 ★ |
| INV-08 | Tasks 2.1, 2.4 | Tasks 2.6 ★, 3.4 ★ |
| INV-09 | Task 2.3 | Tasks 2.6 ★, 3.4 ★ |
| INV-10 | Task 2.4 | Tasks 2.6 ★, 3.4 ★ |
| INV-11 | Task 2.3 | Tasks 2.6 ★, 3.4 ★ |
| INV-12 | Task 1.1 (scaffold — absence) | Tasks 1.1, 3.4 ★ |
| INV-13 | Task 2.2 | Tasks 2.6 ★, 3.4 ★ |
| INV-14 | Task 2.2 | Tasks 2.6 ★, 3.4 ★ |
| INV-15 | Tasks 1.3, 1.4 (static — absence) | Task 3.4 ★ |
| INV-16 | Task 3.1 | Tasks 3.3, 3.4 ★ |
| INV-17 | Tasks 2.4, 2.5 | Tasks 2.6 ★, 3.4 ★ |
| INV-18 | Task 2.5 | Tasks 2.6 ★, 3.4 ★ |

---

## Task Dependency Map

Tasks must execute in this order. A task may not begin until every task it depends on has passed its verification command.

```
1.1 ──┬──────────────────────────────┐
      │                              │
1.2 ──┤                             1.4
      │
1.3 ──┘
      │
    1.5 ★  (Session 1 Gate)
      │
    2.1
    ├── 2.2
    ├── 2.3
    └── 2.1+2.2+2.3 ──► 2.4
                          │
                    2.3+2.4 ──► 2.5
                                  │
                               2.6 ★  (Session 2 Gate)
                                  │
                                3.1
                                ├── 3.2
                                └── 3.3
                                      │
                               3.1+3.2+3.3 ──► 3.4 ★  (Final Gate)
```

★ Gate tasks require engineer sign-off before the next session begins.

---

*Customer Risk API · EXECUTION_PLAN.md v1.1 · DataGrokr Engineering · 2026*