# ARCHITECTURE.MD
**Customer Risk API** · Version 1.0 · DataGrokr Engineering · 2026
*Architecture decision record — Option B selected*

---

## 1. Problem Framing

The Customer Risk API solves a single, precisely scoped problem: controlled, authenticated, read-only access to pre-assessed customer risk tier data. The underlying need is not data processing or risk computation — it is an access control boundary that replaces direct database access with a defined, auditable interface.

Operations staff currently reach risk data through ad-hoc SQL queries against Postgres. This bypasses access controls, exposes the schema to all users, and produces inconsistent output depending on who wrote the query. The API removes direct database access entirely and enforces a contract: one endpoint, one key, one response shape.

**What this system solves:**
- Provides authenticated, structured access to customer risk tier and contributing factors via HTTP GET
- Enforces a single API key authentication boundary so database credentials are never distributed to operations staff
- Serves a browser-accessible UI so operations staff can query without writing code or SQL
- Returns consistent, machine-readable JSON for downstream tool integration
- Guarantees read-only behaviour — the database cannot be modified through this system

**What this system explicitly does not solve:**
- Risk assessment or computation — the database is pre-populated with assessed values; this system only surfaces them
- User management, roles, or multi-key authentication
- Write or update operations on risk data
- Production hardening: TLS termination, rate limiting, secrets management at scale
- Any external service integration — the system is entirely self-contained

---

## 2. Five Key Design Decisions

### DD-01 — Inline HTML returned from a FastAPI route, not a static file

**Decided:** The UI is returned as an `HTMLResponse` from a dedicated `GET /` route. The HTML and embedded JavaScript live in Python source. There is no `StaticFiles` mount and no separate file to deploy.

**Rationale:** Eliminating the static file removes an entire category of deployment misconfiguration. With a `StaticFiles` mount, the file can be missing, the path can be wrong, or the mount can be omitted silently — and the error is only discovered at runtime. With inline HTML, if the API is running, the UI is present. There is no separate file lifecycle to manage.

**Rejected alternatives:**
- *Option A (static file via `StaticFiles` mount):* rejected because a static file is a separate deployment artefact with its own failure mode — path misconfiguration is silent until runtime.
- *Option C (Nginx container for UI):* rejected because Nginx is outside the fixed stack, introduces a third container, requires CORS configuration, and creates the API address problem — JavaScript running in the browser cannot use Docker service names and must know the host-accessible address explicitly.

---

### DD-02 — Auth enforced as a FastAPI route-level dependency, not middleware

**Decided:** The `verify_api_key` function is declared as a dependency on the customer lookup route using FastAPI's `Depends()` injection. It is not applied as global middleware. The `/health` and `/` routes are intentionally unauthenticated.

**Rationale:** Route-level dependency injection is structurally explicit. You can read the route definition and see the auth gate without tracing middleware chains. A dependency on the route cannot be bypassed — if the dependency raises, the route does not execute. This satisfies the requirement that auth is a structural gate, not an afterthought applied post-lookup.

**Rejected alternatives:**
- *Global middleware (FastAPI Middleware or Starlette BaseHTTPMiddleware):* rejected because global middleware applies to all routes by default, meaning `/health` would require an exception list or would be locked behind auth unnecessarily. Exception lists are themselves a source of misconfiguration.

---

### DD-03 — psycopg2 with a new connection per request, no connection pool, no ORM

**Decided:** Each request to the customer endpoint opens a psycopg2 connection, executes a single parameterised `SELECT`, and closes the connection. No connection pool. No ORM.

**Rationale:** The brief mandates psycopg2 and explicitly prohibits an ORM. The no-pool decision follows from the system's read-only, low-concurrency nature: this is an internal operations tool, not a high-throughput service. A per-request connection is simple to reason about, simple to test, and eliminates connection pool state as a failure mode. The SQL is a single `SELECT` — there is no query complexity that an ORM would simplify.

**Rejected alternatives:**
- *SQLAlchemy ORM:* rejected by the brief.
- *asyncpg or connection pooling:* rejected — the brief mandates psycopg2 and the usage profile does not justify pool complexity.
- *Persistent connection on startup:* rejected because a persistent connection creates reconnection complexity if Postgres restarts mid-session.

---

### DD-04 — Postgres initialised and seeded via init.sql on first container start

**Decided:** `db/init.sql` contains the `CREATE TABLE` statement and all `INSERT` rows. Docker's Postgres image executes any `.sql` file mounted to `/docker-entrypoint-initdb.d/` on first start. No migration tooling, no seed scripts, no application-level initialisation.

**Rationale:** The brief requires `docker compose up` to be the full start sequence with no manual steps. Mounting `init.sql` to the Postgres entrypoint directory satisfies this with zero additional tooling. The schema is simple — one table — and seed data is fixed. There is no case in this system for a migration tool.

**Rejected alternatives:**
- *Alembic or Flyway:* rejected — they introduce dependencies and CLI steps that violate the no-manual-setup constraint.
- *Application-level seed logic in main.py:* rejected — the application layer should not own schema creation.
- *A separate seed script:* rejected — it is another manual step outside `docker compose up`.

---

### DD-05 — UI served by the FastAPI container on the same port as the API

**Decided:** `GET /` returns the HTML/JS UI. `GET /customers/{customer_id}` returns JSON. Both are served from the same FastAPI process on port 8000. The JavaScript makes fetch calls to the same origin — no CORS configuration required.

**Rationale:** The brief states the UI must be served by the same container stack and explicitly rules out separate hosting. Serving from the same FastAPI container on the same port satisfies this in the strictest sense: same process, same port, same origin. Same-origin fetch calls require no CORS headers, removing an entire configuration surface.

**Rejected alternatives:**
- *Separate Nginx container in the same Compose file (Option C):* rejected — Nginx is outside the fixed stack, introduces a third container, requires CORS headers on the API, and creates the API address problem in client-side JavaScript.
- *Serving UI from a different port on the same container:* rejected — it adds a second server process and a CORS surface without any benefit.

---

## 3. Challenge My Decisions

### DD-01 — Inline HTML

**Challenge:** Embedding HTML in Python source couples UI changes to API container rebuilds. A non-trivial UI with multiple states becomes hard to read and maintain as an inline string. This is a real maintainability cost.

**Verdict: Challenge rejected.** The UI is intentionally minimal — a text input and a result display. The brief explicitly rules out a frontend framework. At this scope, the deployment simplicity of inline HTML outweighs the maintainability cost. If the UI grew materially, this decision would need revisiting.

---

### DD-02 — Route-level dependency

**Challenge:** Per-route dependency injection requires each new route to declare the auth dependency explicitly. With middleware, new routes are protected by default. A developer adding a route without the dependency creates an unauthenticated endpoint. This is a valid concern for a growing API.

**Verdict: Challenge rejected for this system.** There are three routes — `/health`, `/`, and `/customers/{customer_id}`. The scope boundary in `CLAUDE.md` prohibits Claude Code from adding routes outside the execution plan. The risk of a forgotten dependency on an unauthorised new route is a production codebase concern, not a concern for this controlled, planned build.

---

### DD-03 — Per-request psycopg2 connection

**Challenge:** A new psycopg2 connection per request is expensive under concurrent load. If multiple operations staff query simultaneously, connection overhead compounds. This is not a theoretical concern — it is a real limitation of this design.

**Verdict: Challenge valid but accepted.** The brief explicitly acknowledges this system is not production-hardened. The fixed stack mandates psycopg2 and the brief's out-of-scope list includes production hardening. The constraint is documented here so that any future production adaptation addresses it explicitly.

---

### DD-04 — init.sql via Docker entrypoint

**Challenge:** The `/docker-entrypoint-initdb.d/` mechanism only runs on first container start, when the data volume is empty. If the volume already exists from a prior run, `init.sql` does not re-execute. A developer who runs `docker compose down` without `-v` will have a volume that bypasses seeding on the next `up`. This is a common point of confusion.

**Verdict: Challenge valid and accepted.** This is a known Docker Postgres behaviour. Mitigations: (1) document `docker compose down -v` as the correct teardown in the README, (2) use `CREATE TABLE IF NOT EXISTS` so a partial re-run does not error, (3) the Session 5 integration check explicitly mandates `docker compose down -v` before the final cold-start verification.

---

### DD-05 — Same port, same process

**Challenge:** Serving the UI and API from the same port and process means any failure in the FastAPI process takes down both. There is no independent UI availability. For an operations tool where staff need to query risk tiers during an incident, this is a real operational concern.

**Verdict: Challenge valid but accepted.** The system is explicitly a training demo and internal operations tool, not a production service. The brief's out-of-scope list includes production hardening. Single-process simplicity is the right default for this scope.

---

## 4. Key Risks

| ID | Risk | Description | Mitigation |
|---|---|---|---|
| R-01 | psycopg2 exception surfaces in HTTP response | If a database connection fails or query raises and is not caught, the raw traceback reaches the 500 response body, exposing table names, column names, and connection details. | `get_db_connection` must wrap all psycopg2 exceptions and return a sanitised 500 with a static error message. Verified in Session 3 by stopping the db container and confirming the response body. |
| R-02 | Inline HTML grows beyond maintainability threshold | Embedding HTML in Python source is acceptable at current UI scope. If the UI requires additional states, input validation, or richer display, the inline string becomes difficult to read and modify safely. | Scope boundary in `CLAUDE.md` limits UI complexity. Any material UI change requires a new planning decision, not an inline edit. |
| R-03 | Docker volume bypass of init.sql seeding | If a developer runs `docker compose down` without `-v`, the Postgres data volume persists and `init.sql` does not re-execute on the next `up`. Schema exists but seed data may be stale or missing. | Document `docker compose down -v` as the correct teardown. Session 5 integration check mandates it before cold-start verification. `CREATE TABLE IF NOT EXISTS` prevents duplicate-table errors. |
| R-04 | Single psycopg2 connection per request under concurrent load | Each request opens and closes a psycopg2 connection. Under concurrent usage, connection overhead compounds. Not a production concern given the brief's scope, but invisible as a risk without documentation. | Accepted and documented. Any future adaptation to higher concurrency must replace per-request connections with a pool. |
| R-05 | Auth dependency omitted from a future route | Per-route dependency requires each new route to declare auth explicitly. A developer adding a route without the dependency creates an unauthenticated endpoint. | Scope boundary in `CLAUDE.md` prohibits adding routes outside the execution plan. This risk applies to future development outside PBVI scope. |

---

## 5. Key Assumptions

| ID | Assumption |
|---|---|
| A-01 | A single static API key stored in `.env` is sufficient for this system's authentication requirements. Key rotation and multi-key support are out of scope. |
| A-02 | The seed data in `init.sql` is the authoritative ground truth for all verification. The API is correct if its responses match the database rows exactly. |
| A-03 | Concurrent usage is low enough that per-request psycopg2 connections do not cause observable performance degradation for operations staff. |
| A-04 | The UI scope remains minimal — a text input and a result display — and does not require additional states or interactivity that would make inline HTML unmaintainable. |
| A-05 | Docker Desktop is available and running on the developer's machine. The healthcheck-based startup dependency is sufficient to handle Postgres readiness without manual intervention. |
| A-06 | The `customer_id` format is a string. No format validation beyond existence is required — an ID not found in the database returns 404 regardless of its format. |

---

## 6. Open Questions

| ID | Question |
|---|---|
| OQ-01 | **Factor data structure:** the brief specifies a list of risk factors but does not define the shape. Are factors plain strings or objects with name and description fields? Can the list be empty for any tier? Resolution required before Session 3 schema design. |
| OQ-02 | **404 response shape:** the brief requires a clear 404 but does not specify whether the shape matches the 200 envelope. An inconsistent 404 shape creates integration problems for downstream tools. |
| OQ-03 | **Customer ID format:** is `customer_id` a string, integer, or UUID? The seed data will imply a format, but it is not stated in the brief. The parameterised query must handle whatever type the seed data uses. |
| OQ-04 | **API key format and length:** the brief does not specify. A weak key provides minimal protection even with correct enforcement. Minimum key entropy should be decided before `.env.example` is written. |

---

*DataGrokr Engineering · PBVI Practitioner Series · 2026 · Architecture decision record v1.0*