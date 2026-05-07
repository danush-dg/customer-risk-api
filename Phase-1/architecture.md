# ARCHITECTURE.md
## Customer Risk API

*Version 1.0 · DataGrokr Engineering · 2026*

---

## 1. Problem Framing

### What this system solves

Operations staff need to look up customer risk tier and contributing factors by customer ID. Currently this requires direct database access — bypassing access controls, producing inconsistent query quality, and creating no auditable contract for what was asked or returned. This system places a defined, authenticated interface between consumers and the data.

The two problems being solved are: **uncontrolled data access** (anyone with database credentials can query anything, in any shape) and **operational fragility** (ad-hoc SQL has no enforcement of correctness, missing-customer handling, or response consistency).

### What this system explicitly does not solve

- It does not compute or assess risk. The database is pre-populated with assessed values. The API is a read surface, not a calculation engine.
- It does not audit who queried what. Authentication is enforced; logging of queries for compliance purposes is out of scope.
- It does not manage users, roles, or per-user permissions. One API key, one access level.
- It does not harden for production deployment. No TLS, no rate limiting, no secrets management at scale.
- It does not support writes of any kind. There are no create, update, or delete paths.

---

## 2. Five Key Design Decisions

---

### Decision 1 — Two Docker Compose services, no reverse proxy

**What was decided:** The system runs as two services: `db` (Postgres 15) and `api` (FastAPI). The API container handles all HTTP concerns — REST endpoints, authentication, and static UI serving. No third service.

**Rationale:** The brief specifies a fixed stack. Nginx is not in it. Adding a reverse proxy introduces a third service, a separate configuration artifact, and a new debugging surface — none of which provide functional value for a read-only internal lookup tool. The operational cost is disproportionate to the scale. Two services started by one command is the simplest topology that satisfies all stated constraints.

**Alternatives rejected:**

- *Nginx reverse proxy (Architecture B):* Adds a technology outside the fixed stack, a three-stage startup dependency chain, and an nginx.conf file that can fail in ways that are opaque to a Python developer. Rejected because it violates the fixed stack constraint and introduces complexity the problem does not warrant.
- *Separate UI hosting:* Explicitly prohibited by the brief. Not considered.

---

### Decision 2 — Explicit layered module structure inside the API container

**What was decided:** The FastAPI application is structured as four distinct modules: `router.py` (route definitions only), `auth.py` (API key dependency), `db.py` (all psycopg2 calls), and `schemas.py` (Pydantic response models). `main.py` is the entry point only — it assembles the application and mounts the router. No business logic lives in `main.py`.

**Rationale:** Each invariant maps to exactly one module. During the PBVI code review step, reviewing INV-06 (key never in response) means reading `auth.py` — not scanning `main.py` for every place the key might appear. Reviewing INV-03 (parameterised queries, no writes) means reading `db.py` — one file, complete coverage. This is not over-engineering; it is a direct response to the verification requirements of the build process. Module boundaries are also the isolation seams that make `auth.py` testable without spinning up the full stack.

**Alternatives rejected:**

- *Flat single-module structure (Architecture A):* Satisfies all runtime constraints but makes invariant-to-code traceability a matter of convention. For a PBVI exercise specifically, where code review against named invariants is a required step, convention is not sufficient. Rejected on verification grounds.
- *Logic in `main.py`:* All-in-one is common for small FastAPI projects but conflates routing, auth, and data access in a way that makes targeted review impossible. Rejected.

---

### Decision 3 — Pydantic schemas enforce the response contract at the serialisation boundary

**What was decided:** Response shapes are defined as Pydantic models in `schemas.py`. The customer lookup endpoint declares its return type as the Pydantic model. FastAPI serialises through this model on every response — extra fields from the database are dropped, missing required fields raise an explicit error.

**Rationale:** The response contract must be enforced by the system, not by convention. If the database schema changes and a new column is added, it must not silently appear in API responses. If a required field is missing, it must fail explicitly rather than returning a malformed response. Pydantic at the serialisation boundary provides this guarantee without runtime overhead. It also makes the contract machine-readable — the response shape is defined in one place and enforced everywhere.

**Alternatives rejected:**

- *Return raw psycopg2 row as dict:* Fast to write, but any database schema change silently changes the API response. No enforcement, no contract. Rejected.
- *Manual dict construction in the route handler:* Moves the contract enforcement into imperative code that must be reviewed manually for each field. Fragile and not self-documenting. Rejected.

---

### Decision 4 — psycopg2 directly, no ORM, no connection pool

**What was decided:** Database access uses psycopg2 directly. A new connection is opened per request and closed after. No SQLAlchemy, no connection pool, no ORM.

**Rationale:** The brief explicitly prohibits ORMs. Connection pooling is not prohibited, but it adds complexity — pool lifecycle management, connection leak handling, pool exhaustion behaviour — that is not warranted for a low-concurrency internal tool. A per-request connection is simple, auditable, and safe to reason about. For this scale of system, the overhead of connection setup per request is not a problem. psycopg2's parameterised query support (`%s` placeholders with a tuple of values) is the primary SQL injection defence — keeping the data access layer thin and in one module makes this defence easy to verify.

**Alternatives rejected:**

- *SQLAlchemy ORM:* Explicitly prohibited by the brief. Not considered.
- *SQLAlchemy Core (no ORM):* Permitted by the brief's letter but not its spirit. Adds a dependency and an abstraction layer that obscures the SQL being executed. The brief's intent is direct database access. Rejected.
- *asyncpg with async psycopg2:* Adds async complexity to a system that doesn't need concurrency. uvicorn runs synchronous handlers fine for this load profile. Rejected.

---

### Decision 5 — /health is unauthenticated; all other endpoints require the API key via FastAPI Depends()

**What was decided:** The `/health` endpoint requires no API key. The `/customers/{customer_id}` endpoint has `verify_api_key` as a FastAPI `Depends()` argument — not middleware, not a decorator, not a manual check inside the handler. The `/` route serving the UI HTML requires no API key (the browser loads the page; the page's JavaScript provides the key when it calls the API).

**Rationale:** The Docker Compose healthcheck for the `api` service calls `/health`. If `/health` requires authentication, the healthcheck configuration must pass the API key — which means the key appears in `docker-compose.yml` or requires a secondary env variable. This is unnecessary complexity. `/health` returning `{"status": "ok"}` exposes nothing sensitive. The `/customers/` endpoint is where data lives; that is the boundary that must be authenticated. Using `Depends()` rather than middleware is a deliberate choice: FastAPI middleware can be bypassed by ordering or misconfiguration; a `Depends()` argument on a specific route is attached to exactly that route and cannot be silently skipped.

**Alternatives rejected:**

- *Global middleware for auth:* Applied to all routes including `/health`, requiring either an exception list or a broken healthcheck. Middleware ordering is also a source of subtle bypass bugs. Rejected.
- *Manual key check inside the route handler:* The check becomes part of the handler's logic rather than a declared dependency. It can be forgotten when a new route is added. Rejected.
- *Requiring auth on `/health`:* Makes the Docker healthcheck configuration more complex and exposes the API key in Compose configuration. No security benefit for a health status endpoint. Rejected.

---

## 3. Challenge My Decisions

---

**Challenge 1 — Against: Two services, no reverse proxy**

*Strongest argument against:* FastAPI is a Python ASGI application server. It is not a web server. Serving static files from FastAPI works, but it is not what FastAPI is optimised for. Nginx serves static files from kernel-level sendfile() calls with zero application-layer overhead. For a production system, even an internal one, having Python handle static file serving is an operational smell.

*Assessment:* **Rejected for this system.** The challenge is valid in a production context. It is not valid here. This is explicitly scoped as a training demo system with no production hardening requirements. The operational overhead of nginx — a third service, a config file, a new debugging surface — outweighs the serving efficiency benefit for a single-page UI that will be hit by a handful of operations staff. If this system ever moves toward production, the nginx question reopens.

---

**Challenge 2 — Against: Layered module structure**

*Strongest argument against:* The module boundaries in Architecture C are enforced by discipline, not by the runtime. Nothing in Python prevents `router.py` from importing psycopg2 directly. In a three-week sprint with three developers, the layers will collapse. The structure gives the appearance of separation without the guarantee. A monolith that is honest about being a monolith is easier to maintain than one that pretends to have layers.

*Assessment:* **Partially valid, but rejected.** The challenge correctly identifies that Python module boundaries are not enforced. The counter is that this is a single-developer exercise with explicit code review steps against named invariants. The layers are not there to prevent future developers from violating them — they are there to make the current review step tractable. `db.py` is reviewed for SQL safety. `auth.py` is reviewed for key handling. The structure serves the verification process, not a future team. The challenge would be decisive for a production codebase with multiple contributors; it is not decisive here.

---

**Challenge 3 — Against: Pydantic schemas at the serialisation boundary**

*Strongest argument against:* Pydantic validation adds a serialisation step on every response. For a system that already opens a new database connection per request, adding a validation pass on top means every lookup involves connection setup, query execution, row fetch, connection teardown, and now schema validation. This is unnecessary overhead for a system that returns a known, fixed shape from a stable schema.

*Assessment:* **Rejected.** The overhead is real but negligible at this scale. More importantly, the challenge frames Pydantic as an optimisation concern when its role here is a correctness concern. The schema is the machine-readable contract. It guarantees that a database schema change does not silently change the API response, and that a missing required field fails explicitly rather than returning malformed JSON. The performance cost at this concurrency level is not measurable. The correctness benefit is.

---

**Challenge 4 — Against: Per-request psycopg2 connections, no pool**

*Strongest argument against:* Connection setup is the most expensive part of a database interaction. Even at low concurrency, if ten operations staff hit the lookup endpoint simultaneously, ten connections are opened, used for one query, and closed. A connection pool with a minimum size of two would handle this with a fraction of the setup cost and no code complexity — psycopg2's `psycopg2.pool.SimpleConnectionPool` is four lines.

*Assessment:* **Valid as a general argument, rejected for this system.** The challenge is correct that pooling is cheap to add and reduces connection overhead. It is rejected here for two reasons. First, the brief out-of-scopes production hardening explicitly — pool sizing, leak detection, and exhaustion behaviour are operational concerns that belong in that scope. Second, per-request connections are simpler to reason about for an exercise focused on verification discipline: each request has one connection, no shared state, no leak to debug. The complexity/benefit tradeoff favours simplicity at this scale.

---

**Challenge 5 — Against: /health unauthenticated**

*Strongest argument against:* An unauthenticated endpoint is an unauthenticated information surface, regardless of what it returns. `{"status": "ok"}` today; someone adds a version number or database host to it tomorrow. Once an endpoint is unauthenticated, it tends to stay that way while its response grows. The discipline is to authenticate everything and handle the healthcheck case by passing a designated service key in the Compose configuration.

*Assessment:* **Valid in principle, rejected for this system.** The challenge correctly identifies that unauthenticated endpoints have a tendency to expand. The mitigation is to define the `/health` response shape in `schemas.py` — same as the customer endpoint — so that adding fields to it is a conscious schema decision rather than an ad-hoc addition. For this system, the risk of information leakage from `{"status": "ok"}` is low, and the complexity of injecting an API key into the Compose healthcheck configuration is disproportionate. The response shape is locked by the schema. If this were a production system, the challenge would warrant reconsideration.

---

## 4. Key Risks

**R-1 — SQL injection via customer_id path parameter.** The `customer_id` value arrives as a URL path segment and is passed to psycopg2. If the query in `db.py` is ever constructed with string formatting rather than parameterised placeholders, injection is possible. This risk is mitigated by the layered structure (all SQL lives in `db.py`, reviewed in one place) and by the PBVI invariant check on Session 3. Mitigation: parameterised queries enforced at code review, not just tested.

**R-2 — API key exposure through error responses.** If the `verify_api_key` function in `auth.py` constructs its 401 detail using the submitted key (e.g. `f"Invalid key: {api_key}"`), the key appears in the response body. This is a static detail string discipline problem, not a complex security concern — but it requires explicit review. Mitigation: INV-06 code review step in Session 2, Task 2.4.

**R-3 — Unhandled psycopg2 exceptions surfacing internal state.** A database connection failure at runtime — wrong credentials, db container restarted — will raise a psycopg2 exception. If that exception propagates unhandled to FastAPI's default exception handler, the response body may contain the connection string, the database hostname, or a full Python traceback. Mitigation: explicit try/except in `db.py` with a generic 500 response. This must be in the code review checklist.

**R-4 — Startup race condition between api and db.** If the `depends_on: condition: service_healthy` configuration in `docker-compose.yml` is misconfigured, the API container may start before Postgres is ready and serve connection errors as 500s before the system stabilises. This is an infrastructure configuration risk, not a code risk. Mitigation: Compose healthcheck on the `db` service with appropriate retries and interval, verified in Session 1.

---

## 5. Key Assumptions

- **A-1:** The `customer_id` format is a prefixed string (e.g. `CUST-001`). URL path parameter routing will treat it as a string, not an integer. Seed data will follow this format. *If this assumption is wrong and IDs are integers, path parameter validation changes.*

- **A-2:** Risk factors are stored as an array of plain strings in the database, not as structured objects. The Pydantic schema for the customer response will define `risk_factors` as `list[str]`. *If factors are structured objects with codes and descriptions, the schema and the database column type both change.*

- **A-3:** The `/health` endpoint response shape is `{"status": "ok"}` only. No version information, no database connection status, no additional fields. The shape is frozen in `schemas.py`.

- **A-4:** The API key is a single static value read from the `API_KEY` environment variable. There is no key rotation, no multiple valid keys, and no per-key permissions.

- **A-5:** The seed data contains at least 9 customers — at minimum 3 per tier — to support the invariant test coverage requirements. "Representative" in the brief is interpreted as: each tier must have multiple records, not just one.

- **A-6:** The `.env` file is present on the host machine before `docker compose up` is run. The system does not generate or validate the `.env` file. If it is missing or incomplete, the failure mode is an API container that exits immediately — which is acceptable for a local development system.

---

## 6. Open Questions

**OQ-1 — Risk factor shape:** Assumed to be `list[str]` (see A-2). If this is wrong, the database schema, `schemas.py`, and `index.html` rendering all change. This must be confirmed before `db/init.sql` is written in Session 1.

**OQ-2 — Error response shape consistency:** The 401 response from FastAPI's `HTTPException` and the 404 response have the same default shape (`{"detail": "..."}`). The UI can handle both with the same code path. This should be confirmed as the intended shape rather than defined by FastAPI's default — if the shape ever needs to change, it should be a conscious decision.

**OQ-3 — UI key handling:** The UI must send the API key with each request. Where does the key come from in the browser? Options: hard-coded in `index.html` (acceptable for an internal tool, not for anything else), entered by the user in a second field, or read from a browser environment. This is an implied UI design decision that the brief does not address. *For this system, the key will be entered by the user in a dedicated field alongside the customer ID input — this avoids hard-coding credentials in a file that could be committed.*

**OQ-4 — Container port exposure:** The `api` container exposes port 8000 to the host. The brief does not specify the host port. `8000:8000` is the assumed mapping. If the host machine has a service on 8000, this conflicts. Not blocking, but worth noting in the README.

---

*Customer Risk API · ARCHITECTURE.md v1.0 · DataGrokr Engineering · 2026*