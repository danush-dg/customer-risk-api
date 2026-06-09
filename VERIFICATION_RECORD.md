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
