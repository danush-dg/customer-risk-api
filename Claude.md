# CLAUDE.md — Customer Risk API

## ARCHITECTURE

Two Docker Compose services: `db` (Postgres 15) and `api` (FastAPI, Python 3.11). No reverse proxy. The API container handles all HTTP concerns — REST endpoints, authentication, and static UI serving via FastAPI `StaticFiles`.

**Module structure** (`api/app/`): `main.py` (entry point + startup validation), `router.py` (route definitions only), `auth.py` (API key dependency), `db.py` (all psycopg2 calls), `schemas.py` (Pydantic response models). Each invariant maps to exactly one module — this structure exists to make code review against named invariants tractable, not for runtime enforcement.

**Key decisions:** psycopg2 direct — no ORM, no pool, per-request connection. Pydantic at the serialisation boundary enforces the response contract (`extra='forbid'`). Auth via `Depends(verify_api_key)` on the route, not middleware — middleware can be bypassed by ordering. `/health` is unauthenticated; `GET /customers/{customer_id}` and `GET /` are the only other routes. `API_KEY` validated at module load before `app = FastAPI()` — process exits non-zero if absent, empty, or fewer than 16 characters.

**Fixed stack:** Docker Compose · Postgres · FastAPI · psycopg2 · plain HTML + vanilla JS. No external service calls. System is read-only — no write endpoints exist.

---

## INVARIANTS

Eighteen invariants govern this system. **If a task conflicts with an invariant, the invariant wins. Flag the conflict; never resolve it silently.**

| ID | Category | Rule (one line) |
|---|---|---|
| INV-01 | Data correctness | API response values match DB character-for-character; `CHECK (risk_tier IN ('LOW','MEDIUM','HIGH'))` enforced in schema |
| INV-02 | Data correctness | Every DB customer is retrievable; lookup is exact-match, case-sensitive |
| INV-03 | Existence mapping | Missing customer → 404, body exactly `{"detail": "Customer not found"}` |
| INV-04 | Existence mapping | 404 detail is a string literal — no f-string, no reflection of submitted value |
| INV-05 | Mutability | No request causes a DB write; three specified injection strings must be tested post-call with row count check |
| INV-06 | Mutability | `init.sql` contains no `CREATE TRIGGER` or `CREATE FUNCTION` — static review only |
| INV-07 | Response shape | Every 200 contains exactly `customer_id`, `risk_tier`, `risk_factors`; `extra='forbid'` on `CustomerResponse` |
| INV-08 | Response shape | `risk_tier` is exactly `LOW`, `MEDIUM`, or `HIGH`; route decorator must have `response_model=CustomerResponse` and handler `-> CustomerResponse` |
| INV-09 | Authentication | No valid `X-API-Key` → 401; missing header must return 401 not 422 (requires `Header(default=None)`) |
| INV-10 | Authentication | `/health` unauthenticated; body exactly `{"status": "ok"}`; `HealthResponse` with `extra='forbid'` and `response_model=` on decorator |
| INV-11 | Credential handling | API key never appears in any response body at any status code |
| INV-12 | Credential handling | `.env` never in version control — both working-tree (`git ls-files`) and history (`git log --all`) checks required |
| INV-13 | Error surfaces | DB failure → `{"detail": "Internal server error"}` only; `str(e)` in detail prohibited |
| INV-14 | Error surfaces | Every `db.py` function has both `except psycopg2.Error` and bare `except Exception`; no exception variable in `raise` |
| INV-15 | Operational isolation | No outbound calls outside Docker Compose internal network; no `requests`/`httpx` in `requirements.txt` |
| INV-16 | UI fidelity | All API values rendered verbatim via `textContent` (never `innerHTML`); no tier-to-label mapping; error path shows raw `detail` and HTTP status code |
| INV-17 | Route completeness | Exactly `GET /`, `GET /health`, `GET /customers/{customer_id}` — nothing else |
| INV-18 | Startup validation | Process exits non-zero before binding if `API_KEY` is absent, empty, or < 16 characters |

---

## EXECUTION PLAN

Three sessions in strict dependency order. Gates require engineer sign-off — Claude never declares a gate passed.

**Session 1 — Infrastructure & Data** (Tasks 1.1–1.5★)
`1.1` Repo scaffold + `.gitignore` → `1.2` `db/init.sql` (schema + 9 seed rows, 3 per tier, one with empty `risk_factors`) → `1.3` `docker-compose.yml` (healthcheck, no hardcoded secrets, internal network only) → `1.4` `Dockerfile` + `requirements.txt` (exactly 4 packages, no HTTP clients) → `1.5★` Gate: both containers healthy, 9 rows present, CHECK constraint active, no triggers in `init.sql`.

**Session 2 — API Service** (Tasks 2.1–2.6★)
`2.1` `schemas.py` (two models, `extra='forbid'` on both) → `2.2` `db.py` (`RealDictCursor`, parameterised queries, dual-clause exception handling, static 404/500 literals) → `2.3` `auth.py` (`Header(default=None)`, static 401 literal, no key logging) → `2.4` `router.py` (two routes, `response_model` and return type on both, `Depends(verify_api_key)` on customer route) → `2.5` `main.py` (startup validation before `app = FastAPI()`, static mount, root route, router included) → `2.6★` Gate: full auth sweep, injection tests, response shape, DB-down 500, startup validation.

**Session 3 — UI & System Validation** (Tasks 3.1–3.4★)
`3.1` `ui/index.html` (two inputs, `textContent` only, verbatim render on all paths including errors) → `3.2` Static serving verification (`GET /` → 200, API routes not shadowed) → `3.3` INV-16 static code review (five criteria) → `3.4★` Final gate: all 18 invariants checked off by engineer individually.

**Dependency order:** 1.1 → 1.2 → 1.3 → 1.4 → 1.5★ → 2.1 → {2.2, 2.3} → 2.4 → 2.5 → 2.6★ → 3.1 → {3.2, 3.3} → 3.4★

---

## SESSION STATE

| Field | Value |
|---|---|
| Current session | — |
| Current task | — |
| Last gate passed | — |
| Open questions | OQ-3 resolved: API key entered by user in UI field. OQ-1–OQ-4 otherwise open until Session 1 gate. |
| Flags | None |