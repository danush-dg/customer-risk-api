# VERIFICATION_RECORD.MD
**Customer Risk API** · Session 1 — Project Scaffold and Database
**Branch:** `session/s01_scaffold`

---

## Task S1.T1 — Create the project directory structure

**Invariants touched:** None

### Verification

| Field | Value |
|---|---|
| Verification command | `find customer-risk-api -type f \| sort` |
| Prediction statement | |

| Scenario | Expected | Result | Verdict |
|---|---|---|---|
| All 7 file paths present | `customer-risk-api/.env.example`, `customer-risk-api/README.md`, `customer-risk-api/api/Dockerfile`, `customer-risk-api/api/main.py`, `customer-risk-api/api/requirements.txt`, `customer-risk-api/db/init.sql`, `customer-risk-api/docker-compose.yml` | | ☐ PASS ☐ FAIL |
| All files empty or placeholder only | No content beyond a single placeholder comment in any file | | ☐ PASS ☐ FAIL |
| No additional files or directories present | Exactly 7 paths returned, no extras | | ☐ PASS ☐ FAIL |

### CD Challenge

| Field | Value |
|---|---|
| Prompt sent | `What did you not test in this task?` |
| CD output | |
| Gaps accepted | |
| Gaps rejected (with reason) | |

### Overall Verdict

☐ PASS — all scenarios verified, no unresolved gaps
☐ FAIL — reason:

---

## Task S1.T2 — Write the database schema and seed data

**Invariants touched:** INV-01, INV-03, INV-05, INV-06

### Verification

| Field | Value |
|---|---|
| Verification command 1 | `docker compose exec db psql -U riskuser -d riskdb -c "SELECT risk_tier, COUNT(*) FROM customer_risk_profiles GROUP BY risk_tier ORDER BY risk_tier;"` |
| Verification command 2 | `docker compose exec db psql -U riskuser -d riskdb -c "\d customer_risk_profiles"` |
| Prediction statement | |

| Scenario | Expected | Result | Verdict |
|---|---|---|---|
| Tier distribution | Three rows: HIGH 3+, LOW 3+, MEDIUM 3+ | | ☐ PASS ☐ FAIL |
| `risk_factors` column type | Column shows type `text[]` — not VARCHAR or TEXT | | ☐ PASS ☐ FAIL |
| `CREATE TABLE IF NOT EXISTS` present | Statement present in init.sql | | ☐ PASS ☐ FAIL |
| CHECK constraint present | Constraint limits risk_tier to LOW, MEDIUM, HIGH | | ☐ PASS ☐ FAIL |
| No write definitions | No UPDATE, DELETE, trigger, or function definitions in init.sql | | ☐ PASS ☐ FAIL |
| `risk_factors` seeded as array literal | Each INSERT row uses array literal syntax, not a plain string | | ☐ PASS ☐ FAIL |

### Code Review

| Check | Result |
|---|---|
| No UPDATE, DELETE, or trigger definitions | |
| CHECK constraint present and correct | |
| `risk_factors` column is `TEXT[]` not `VARCHAR` | |

### CD Challenge

| Field | Value |
|---|---|
| Prompt sent | `What did you not test in this task? Focus on INV-01 and INV-03 — could an implementation pass all these cases while still violating either?` |
| CD output | |
| Gaps accepted | |
| Gaps rejected (with reason) | |

### Overall Verdict

☐ PASS — all scenarios verified, code review complete, no unresolved gaps
☐ FAIL — reason:

---

## Task S1.T3 — Write docker-compose.yml and .env.example

**Invariants touched:** INV-02, INV-07, INV-10

### Verification

| Field | Value |
|---|---|
| Verification command 1 | `cd customer-risk-api && docker compose config --quiet && echo "Config valid"` |
| Verification command 2 | `docker compose config \| grep -A5 "healthcheck"` |
| Prediction statement | |

| Scenario | Expected | Result | Verdict |
|---|---|---|---|
| Compose config valid | Output: `Config valid` with no errors | | ☐ PASS ☐ FAIL |
| Healthcheck uses `pg_isready` | Healthcheck block shows `pg_isready` — not a TCP check or sleep | | ☐ PASS ☐ FAIL |
| `api` depends_on `db` with `service_healthy` | `condition: service_healthy` present under api depends_on | | ☐ PASS ☐ FAIL |
| No external network definitions | No `networks:` block with `external: true` | | ☐ PASS ☐ FAIL |
| All six `.env.example` keys present | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `API_KEY` all present | | ☐ PASS ☐ FAIL |
| `POSTGRES_HOST` set to `db` | Value is `db` — not `localhost` | | ☐ PASS ☐ FAIL |

### Code Review

| Check | Result |
|---|---|
| No `networks:` block with `external: true` | |
| Healthcheck command is `pg_isready` | |
| Healthcheck interval ≤ 10s and retries ≥ 3 | |
| `POSTGRES_HOST=db` in .env.example | |

### CD Challenge

| Field | Value |
|---|---|
| Prompt sent | `What did you not test in this task? Focus on INV-10 — could an implementation pass all these cases while still violating it?` |
| CD output | |
| Gaps accepted | |
| Gaps rejected (with reason) | |

### Overall Verdict

☐ PASS — all scenarios verified, code review complete, no unresolved gaps
☐ FAIL — reason:

---

## Session 1 Integration Check

```bash
cd customer-risk-api
cp .env.example .env
# Edit .env — set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, API_KEY
docker compose up db -d
sleep 8
docker compose exec db psql -U riskuser -d riskdb \
  -c "SELECT customer_id, risk_tier FROM customer_risk_profiles ORDER BY risk_tier, customer_id;"
```

| Expected | Result | Verdict |
|---|---|---|
| 9+ rows returned, all three tiers present, no errors | | ☐ PASS ☐ FAIL |

---

*DataGrokr Engineering · PBVI Practitioner Series · 2026*