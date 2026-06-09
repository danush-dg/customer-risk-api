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
| Prediction statement | Running `find customer-risk-api -type f \| sort` will return exactly 7 paths — one for each scaffolded file — in alphabetical order. No additional paths will be present. All files will contain only a single placeholder comment. |

| Scenario | Expected | Result | Verdict |
|---|---|---|---|
| All 7 file paths present | `customer-risk-api/.env.example`, `customer-risk-api/README.md`, `customer-risk-api/api/Dockerfile`, `customer-risk-api/api/main.py`, `customer-risk-api/api/requirements.txt`, `customer-risk-api/db/init.sql`, `customer-risk-api/docker-compose.yml` | All 7 paths returned in correct order | ☑ PASS ☐ FAIL |
| All files empty or placeholder only | No content beyond a single placeholder comment in any file | Each file contained only a `# placeholder` or `-- placeholder` comment at creation | ☑ PASS ☐ FAIL |
| No additional files or directories present | Exactly 7 paths returned, no extras | Exactly 7 paths, no extras | ☑ PASS ☐ FAIL |

### CD Challenge

| Field | Value |
|---|---|
| Prompt sent | `What did you not test in this task?` |
| CD output | The verification confirms file paths exist but does not assert file contents are *only* a placeholder — a file with placeholder plus other content would pass the path check. Also does not verify that directories themselves contain no extra subdirectories. |
| Gaps accepted | Path-existence check sufficient for scaffold task. Content emptiness confirmed by direct inspection. |
| Gaps rejected (with reason) | None |

### Overall Verdict

☑ PASS — all scenarios verified, no unresolved gaps
☐ FAIL — reason:

---

## Task S1.T2 — Write the database schema and seed data

**Invariants touched:** INV-01, INV-03, INV-05, INV-06

### Verification

| Field | Value |
|---|---|
| Verification command 1 | `docker compose exec db psql -U postgres -d customer-risk-api -c "SELECT risk_tier, COUNT(*) FROM customer_risk_profiles GROUP BY risk_tier ORDER BY risk_tier;"` |
| Verification command 2 | `docker compose exec db psql -U postgres -d customer-risk-api -c "\d customer_risk_profiles"` |
| Prediction statement | Command 1 will return exactly 3 rows: HIGH 3, LOW 3, MEDIUM 3. Command 2 will show `risk_factors` with type `text[]`. The CHECK constraint and NOT NULL constraints will be visible in the table description. |

| Scenario | Expected | Result | Verdict |
|---|---|---|---|
| Tier distribution | Three rows: HIGH 3, LOW 3, MEDIUM 3 | HIGH 3, LOW 3, MEDIUM 3 — 9 total rows across 3 tiers | ☑ PASS ☐ FAIL |
| `risk_factors` column type | Column shows type `text[]` — not VARCHAR or TEXT | `risk_factors text[] NOT NULL` confirmed in schema | ☑ PASS ☐ FAIL |
| `CREATE TABLE IF NOT EXISTS` present | Statement present in init.sql | Present on line 1 of init.sql | ☑ PASS ☐ FAIL |
| CHECK constraint present | Constraint limits risk_tier to LOW, MEDIUM, HIGH | `CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))` on line 3 | ☑ PASS ☐ FAIL |
| No write definitions | No UPDATE, DELETE, trigger, or function definitions in init.sql | grep returned no matches for UPDATE, DELETE, TRIGGER, FUNCTION | ☑ PASS ☐ FAIL |
| `risk_factors` seeded as array literal | Each INSERT row uses array literal syntax, not a plain string | All 9 INSERT rows use `ARRAY[...]` syntax | ☑ PASS ☐ FAIL |

### Code Review

| Check | Result |
|---|---|
| No UPDATE, DELETE, or trigger definitions | PASS — grep confirmed no matches |
| CHECK constraint present and correct | PASS — `CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))` present on column definition |
| `risk_factors` column is `TEXT[]` not `VARCHAR` | PASS — column declared as `TEXT[] NOT NULL` |

### CD Challenge

| Field | Value |
|---|---|
| Prompt sent | `What did you not test in this task? Focus on INV-01 and INV-03 — could an implementation pass all these cases while still violating either?` |
| CD output | INV-01: The verification confirms row counts by tier but does not compare individual field values (risk_factors content) against what the API will return — a mismatch between seed data and API response would not be caught here. That gap is closed in S3.T2. INV-03: The tests confirm no write statements in init.sql but do not verify that Postgres grants on the runtime user prevent writes at the database level — a future session could add an INSERT-capable route and the DB would permit it. |
| Gaps accepted | INV-01 data fidelity gap accepted — closed by S3.T2 direct DB-to-API comparison. INV-03 DB-level grant check accepted as out of scope for this stack (single-user Compose setup). |
| Gaps rejected (with reason) | None |

### Overall Verdict

☑ PASS — all scenarios verified, code review complete, no unresolved gaps
☐ FAIL — reason:

---

## Task S1.T3 — Write docker-compose.yml and .env.example

**Invariants touched:** INV-02, INV-07, INV-10

### Verification

| Field | Value |
|---|---|
| Verification command 1 | `cd customer-risk-api && docker compose config --quiet && echo "Config valid"` |
| Verification command 2 | `docker compose config \| grep -A5 "healthcheck"` |
| Prediction statement | Command 1 will exit 0 and print `Config valid`. Command 2 will show a healthcheck block containing `pg_isready`, with interval 5s and retries 5. No `external: true` will appear anywhere. |

| Scenario | Expected | Result | Verdict |
|---|---|---|---|
| Compose config valid | Output: `Config valid` with no errors | `Config valid` — exit 0 | ☑ PASS ☐ FAIL |
| Healthcheck uses `pg_isready` | Healthcheck block shows `pg_isready` — not a TCP check or sleep | `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` confirmed | ☑ PASS ☐ FAIL |
| `api` depends_on `db` with `service_healthy` | `condition: service_healthy` present under api depends_on | `condition: service_healthy` present in api service block | ☑ PASS ☐ FAIL |
| No external network definitions | No `networks:` block with `external: true` | No `networks:` block in docker-compose.yml | ☑ PASS ☐ FAIL |
| All six `.env.example` keys present | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `API_KEY` all present | All 6 keys present | ☑ PASS ☐ FAIL |
| `POSTGRES_HOST` set to `db` | Value is `db` — not `localhost` | `POSTGRES_HOST=db` confirmed | ☑ PASS ☐ FAIL |

### Code Review

| Check | Result |
|---|---|
| No `networks:` block with `external: true` | PASS — no networks block present |
| Healthcheck command is `pg_isready` | PASS — `CMD-SHELL` with `pg_isready` |
| Healthcheck interval ≤ 10s and retries ≥ 3 | PASS — interval 5s, retries 5 |
| `POSTGRES_HOST=db` in .env.example | PASS — confirmed |

### CD Challenge

| Field | Value |
|---|---|
| Prompt sent | `What did you not test in this task? Focus on INV-10 — could an implementation pass all these cases while still violating it?` |
| CD output | The config check confirms no external network definitions in docker-compose.yml but does not verify that application code makes no outbound calls — a `requests.get(...)` in main.py would violate INV-10 and pass all these checks. That gap is tested explicitly in S5.T2 with a grep over main.py imports. |
| Gaps accepted | INV-10 application-level check accepted — closed by S5.T2 import grep. |
| Gaps rejected (with reason) | None |

### Overall Verdict

☑ PASS — all scenarios verified, code review complete, no unresolved gaps
☐ FAIL — reason:

---

## Session 1 Integration Check

```bash
cd customer-risk-api
cp .env.example .env
docker compose up db -d
# wait ~10s
docker compose exec db psql -U postgres -d customer-risk-api \
  -c "SELECT customer_id, risk_tier FROM customer_risk_profiles ORDER BY risk_tier, customer_id;"
```

| Expected | Result | Verdict |
|---|---|---|
| 9+ rows returned, all three tiers present, no errors | 9 rows returned: CUST-007/008/009 HIGH, CUST-001/002/003 LOW, CUST-004/005/006 MEDIUM | ☑ PASS ☐ FAIL |

---

*DataGrokr Engineering · PBVI Practitioner Series · 2026*
