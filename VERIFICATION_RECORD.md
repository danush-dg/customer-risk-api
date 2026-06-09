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
cd customer-risk-api && docker compose build api 2>&1 | tail -5
grep "FROM" customer-risk-api/api/Dockerfile
```
**Output:** PENDING
**Result:** PENDING

---

### T2.2 — Health endpoint returns exactly `{"status": "ok"}`
**Command:**
```
curl -s http://localhost:8000/health | python3 -c \
  "import sys, json; d=json.load(sys.stdin); assert list(d.keys())==['status'], f'Extra fields: {d}'; print('PASS')"
```
**Output:** PENDING
**Result:** PENDING

---

### T2.3 — DB connection function — success case
**Command:**
```
docker compose exec api python -c "import main; conn = main.get_db_connection(); print('PASS' if conn else 'FAIL')"
```
**Output:** PENDING
**Result:** PENDING

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
**Output:** PENDING
**Result:** PENDING

---

### T2.4 — Auth dependency rejects wrong key
**Command:**
```
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
**Output:** PENDING
**Result:** PENDING

---

### Session 2 Integration Check
**Commands:**
```
curl -s http://localhost:8000/health
curl -s http://localhost:8000/customers/CUST-001
curl -s -H "X-API-Key: wrong" http://localhost:8000/customers/CUST-001
```
**Output:** PENDING
**Result:** PENDING
