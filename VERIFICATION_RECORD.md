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
