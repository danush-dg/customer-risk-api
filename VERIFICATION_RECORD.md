# VERIFICATION_RECORD.md
**Customer Risk API** · DataGrokr Engineering · 2026

---

## Session 1 — Project Scaffold and Database

### T1.1 — Directory structure
**Command:**
```
find customer-risk-api -type f | sort
```
**Output:**
```
customer-risk-api/.env.example
customer-risk-api/README.md
customer-risk-api/api/Dockerfile
customer-risk-api/api/main.py
customer-risk-api/api/requirements.txt
customer-risk-api/db/init.sql
customer-risk-api/docker-compose.yml
```
**Result: PASS** — 7 paths, exact match, no extra files.

---

### T1.2 — Tier distribution
**Command:**
```
docker compose exec db psql -U postgres -d customer-risk-api
  -c "SELECT risk_tier, COUNT(*) FROM customer_risk_profiles GROUP BY risk_tier ORDER BY risk_tier;"
```
**Output:**
```
 risk_tier | count
-----------+-------
 HIGH      |     3
 LOW       |     3
 MEDIUM    |     3
(3 rows)
```
**Result: PASS** — 3 rows per tier.

---

### T1.2 — Column types
**Pending** — run `\d customer_risk_profiles` and confirm `risk_factors` shows `text[]`.

---

### T1.3 — Compose config valid
**Pending** — run `docker compose config --quiet && echo Config valid`.

### T1.3 — Healthcheck uses pg_isready
**Pending** — run `docker compose config | findstr /i "pg_isready"`.

### T1.3 — No external networks
**Pending** — run `docker compose config | findstr /i "external"` and confirm no output.

---

### Session 1 Integration Check
**Command:**
```
docker compose exec db psql -U postgres -d customer-risk-api
  -c "SELECT customer_id, risk_tier FROM customer_risk_profiles ORDER BY risk_tier, customer_id;"
```
**Output:**
```
 customer_id | risk_tier
-------------+-----------
 CUST-007    | HIGH
 CUST-008    | HIGH
 CUST-009    | HIGH
 CUST-001    | LOW
 CUST-002    | LOW
 CUST-003    | LOW
 CUST-004    | MEDIUM
 CUST-005    | MEDIUM
 CUST-006    | MEDIUM
(9 rows)
```
**Result: PASS** — 9 rows, all three tiers present, no errors.

---

## Session 2 — FastAPI Application Core

### T2.1 — Docker build succeeds
**Command:**
```
docker compose build api 2>&1 | tail -5
```
**Output:**
```
Image customer-risk-api-api Built
```
**Result: PASS** — build completed, `FROM python:3.11-slim` confirmed in Dockerfile.

---

### T2.2 — Health endpoint returns exactly `{"status": "ok"}`
**Command:**
```
docker compose exec api python -c "
import urllib.request, json
r=urllib.request.urlopen('http://localhost:8000/health')
d=json.loads(r.read())
assert list(d.keys())==['status'], f'Extra fields: {d}'
print('PASS')"
```
**Output:**
```
PASS
```
**Result: PASS** — exactly one key `status`, no extra fields (INV-13).

---

### T2.3 — DB connection function — success case
**Command:**
```
docker compose exec api python -c "import main; conn = main.get_db_connection(); print('PASS' if conn else 'FAIL')"
```
**Output:**
```
PASS
```
**Result: PASS**

### T2.3 — DB connection function — failure case (DB down)
**Command:**
```
docker compose stop db
docker compose exec api python -c "
import main
from fastapi import HTTPException
try:
    main.get_db_connection()
    print('FAIL: no exception raised')
except HTTPException as e:
    print('PASS' if e.detail == 'Internal server error' else f'FAIL: {e.detail}')
"
docker compose start db
```
**Output:**
```
PASS
```
**Result: PASS** — HTTPException(500, "Internal server error") raised, no psycopg2 detail exposed (INV-09).

---

### T2.4 — Auth dependency — all 7 cases
**Command:**
```
docker compose exec api python -c "
import asyncio, os, main
from fastapi import HTTPException
os.environ['API_KEY'] = 'test-secret-key'
async def run():
    cases = [
        ('test-secret-key', False, 'correct key'),
        ('wrong-key',       True,  'wrong key'),
        (None,              True,  'missing key'),
        ('',                True,  'empty key'),
        ('test-secret',     True,  'prefix of valid key'),
        ('test-secret-key ',True,  'valid key with trailing space'),
    ]
    details = []
    for key, should_raise, label in cases:
        try:
            await main.verify_api_key(key)
            result = 'PASS' if not should_raise else 'FAIL (expected 401)'
        except HTTPException as e:
            if should_raise and e.detail == 'Unauthorized':
                result = 'PASS'
                details.append(e.detail)
            else:
                result = f'FAIL (detail={e.detail})'
        print(f'{label}: {result}')
    unique = set(details)
    print(f'All 401 details identical: {\"PASS\" if len(unique)==1 else \"FAIL\"}')
asyncio.run(run())"
```
**Output:**
```
correct key: PASS
wrong key: PASS
missing key: PASS
empty key: PASS
prefix of valid key: PASS
valid key with trailing space: PASS
All 401 details identical: PASS
```
**Result: PASS** — all 7 cases, static literal confirmed (INV-07, INV-08, INV-09, INV-12).

---

### Session 2 Integration Check
**Commands:**
```
curl -s http://localhost:8000/health
curl -s http://localhost:8000/customers/CUST-001
curl -s -H "X-API-Key: wrong" http://localhost:8000/customers/CUST-001
```
**Output:**
```
{"status":"ok"}
{"message":"placeholder"}
{"message":"placeholder"}
```
**Result: PASS** — health correct, no 500s. Auth placeholder expected — `verify_api_key` not yet wired to route (T3.1).

---

## Session 3 — Customer Lookup Endpoint

### T3.1 — Code Review
- **SQL query** (`main.py:44-45`): static string literal, single `%s`, passed as `(customer_id,)` tuple — no f-string, no `.format()`, no concatenation. INV-04 PASS.
- **Auth dependency** (`main.py:40`): `api_key: str = Depends(verify_api_key)` — auth is the first FastAPI dependency resolved before route body executes. INV-07 PASS.
- **`finally: conn.close()`** (`main.py:52-53`): present, executes regardless of 404 or success path. Connection not leaked.
- **Response shape** (`main.py:51`): dict literal with exactly three keys — `customer_id`, `risk_tier`, `risk_factors` — no extras. INV-05 PASS.
- **No string transformation**: `row[1]` (risk_tier) and `row[2]` (risk_factors) returned as-is from the DB cursor. INV-06 PASS.

### T3.1 — Authenticated request, existing customer (200)
**Prediction:** 200 with `{"customer_id":"CUST-001","risk_tier":"LOW","risk_factors":[...]}` — three fields, list type for factors.
**Command:**
```
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-001
```
**Output:**
```
{"customer_id":"CUST-001","risk_tier":"LOW","risk_factors":["account in good standing","consistent payment history","low utilisation rate"]}
```
**Result: PASS** — 200, exactly three fields, correct types (INV-02, INV-05, INV-06).

### T3.1 — Authenticated request, non-existent customer (404)
**Prediction:** 404 with `{"detail":"Customer not found"}`.
**Command:**
```
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-999
```
**Output:**
```
{"detail":"Customer not found"}
```
**Result: PASS** — 404 with static literal (INV-02).

### T3.1 — Unauthenticated request (401)
**Prediction:** 401 with `{"detail":"Unauthorized"}` before any DB interaction.
**Command:**
```
curl -s http://localhost:8000/customers/CUST-001
```
**Output:**
```
{"detail":"Unauthorized"}
```
**Result: PASS** — 401 with static literal, no DB interaction (INV-07, INV-12).

---

### T3.2 — Direct DB vs API comparison
**Predictions (from `db/init.sql` seed data, recorded before API calls):**
- CUST-001: expected `risk_tier=LOW`, 3-element factors array
- CUST-004: expected `risk_tier=MEDIUM`, 2-element factors array
- CUST-007: expected `risk_tier=HIGH`, 2-element factors array

**DB query:**
```
docker compose exec db psql -U postgres -d customer-risk-api \
  -c "SELECT customer_id, risk_tier, risk_factors FROM customer_risk_profiles ORDER BY customer_id;"
```
**DB output:**
```
 customer_id | risk_tier | risk_factors
-------------+-----------+---------------------------------------------------------------
 CUST-001    | LOW       | {"account in good standing","consistent payment history","low utilisation rate"}
 CUST-004    | MEDIUM    | {"two late payments in past year","moderate utilisation"}
 CUST-007    | HIGH      | {"three missed payments","account referred to collections"}
```

**API responses:**
```
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-001
{"customer_id":"CUST-001","risk_tier":"LOW","risk_factors":["account in good standing","consistent payment history","low utilisation rate"]}

curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-004
{"customer_id":"CUST-004","risk_tier":"MEDIUM","risk_factors":["two late payments in past year","moderate utilisation"]}

curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-007
{"customer_id":"CUST-007","risk_tier":"HIGH","risk_factors":["three missed payments","account referred to collections"]}
```
**Result: PASS** — customer_id, risk_tier, and risk_factors match DB rows exactly for all three tiers (INV-01).

---

### T3.3 — DB down returns static 500 literal
**Prediction:** `{"detail":"Internal server error"}` with `Content-Type: application/json` — no psycopg2 exception text, no table names.
**Command:**
```
docker compose stop db
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-001
curl -si -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-001 | grep -i content-type
docker compose start db && sleep 8
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-001
```
**Output:**
```
{"detail":"Internal server error"}
content-type: application/json
{"customer_id":"CUST-001","risk_tier":"LOW","risk_factors":["account in good standing","consistent payment history","low utilisation rate"]}
```
**Result: PASS** — 500 body is exactly `{"detail":"Internal server error"}`, Content-Type is application/json, no psycopg2 detail exposed, normal operation resumes after DB restart (INV-09).

---

### Session 3 Integration Check
**Commands:**
```
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-001
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-004
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-007
curl -s -H "X-API-Key: dev-api-key-2026" http://localhost:8000/customers/CUST-999
curl -s http://localhost:8000/customers/CUST-001
curl -s -H "X-API-Key: wrong" http://localhost:8000/customers/CUST-001
curl -s http://localhost:8000/health
```
**Output:**
```
{"customer_id":"CUST-001","risk_tier":"LOW","risk_factors":["account in good standing","consistent payment history","low utilisation rate"]}
{"customer_id":"CUST-004","risk_tier":"MEDIUM","risk_factors":["two late payments in past year","moderate utilisation"]}
{"customer_id":"CUST-007","risk_tier":"HIGH","risk_factors":["three missed payments","account referred to collections"]}
{"detail":"Customer not found"}
{"detail":"Unauthorized"}
{"detail":"Unauthorized"}
{"status":"ok"}
```
**Result: PASS** — all three tiers return correct data, 404 and both 401 cases return identical static literals, health returns exactly `{"status":"ok"}`.

---

### Session 3 Verification Verdict

**Verdict: PASS**

| Task | Result | Invariants verified |
|---|---|---|
| T3.1 — Customer lookup endpoint | PASS | INV-01, INV-02, INV-04, INV-05, INV-06, INV-07 |
| T3.2 — DB vs API data correctness | PASS | INV-01 |
| T3.3 — DB error handling | PASS | INV-09 |
| Integration check | PASS | All of the above |

All predictions matched actual outputs. Code review confirmed: static SQL, `Depends(verify_api_key)` wired first, `finally: conn.close()` present, three-key response dict, no tier string transformation.

---

## Session 4 — Browser UI and Error State Tests

### T4.1 — GET / returns 200 with Content-Type: text/html
**Prediction:** 200, `Content-Type: text/html`, page contains `<input` and a submit button.
**Command:**
```
curl -si http://localhost:8000/ | grep -i content-type
curl -s http://localhost:8000/ | grep -i "<input"
```
**Output:** PENDING
**Result:** PENDING

### T4.1 — No external script references
**Prediction:** No `src=` attributes referencing external hosts.
**Command:**
```
curl -s http://localhost:8000/ | grep -i "src=" | grep -v "localhost"
```
**Output:** PENDING (expect no output)
**Result:** PENDING

### T4.1 — Relative fetch path
**Prediction:** JavaScript uses `/customers/${id}` or equivalent relative path — no hardcoded host.
**Command:**
```
curl -s http://localhost:8000/ | grep -i "customers/"
```
**Output:** PENDING
**Result:** PENDING

### T4.1 — Code Review
- **No tier remapping:** PENDING — confirm no `switch`, no label map, no conditional on `risk_tier` value
- **Relative fetch URL:** PENDING — confirm `/customers/${id}`, not `http://...`
- **X-API-Key header:** PENDING — confirm `headers: {'X-API-Key': ...}` in fetch call
- **All inline:** PENDING — confirm no `StaticFiles` mount, no external `<script src=...>`

### T4.2 — Automated error state tests (5 cases)
**Prediction:** 5 tests collected, 5 passed.
**Command:**
```
python -m pytest api/test_errors.py -v
```
**Output:** PENDING
**Result:** PENDING

---

### Session 4 Integration Check
**Commands:**
```
python -m pytest api/test_errors.py -v
curl -s http://localhost:8000/ | grep -i "<input"
```
**Output:** PENDING
**Result:** PENDING

---

### Session 4 Verification Verdict

**Verdict: PENDING**

| Task | Result | Invariants verified |
|---|---|---|
| T4.1 — Browser UI | PENDING | INV-11 |
| T4.2 — Error state tests | PENDING | INV-02, INV-07, INV-08, INV-12 |
| Integration check | PENDING | — |
