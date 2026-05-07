Move 2 — Solution Exploration

Candidate Architecture A — Single Container, FastAPI Serves Everything
What it is
One FastAPI container handles all responsibilities: it serves the REST endpoint, enforces authentication, connects directly to Postgres via psycopg2, and also serves the HTML/JS UI as a static file from the same process. Docker Compose runs two services: db (Postgres) and api (FastAPI). The UI is a single index.html file that the FastAPI app serves via a route — no separate web server, no additional container.
┌─────────────────────────────────────────┐
│  Docker Compose                         │
│                                         │
│  ┌──────────┐      ┌─────────────────┐  │
│  │ db       │◄─────│ api             │  │
│  │ Postgres │      │ FastAPI         │  │
│  │ :5432    │      │ :8000           │  │
│  └──────────┘      │  /health        │  │
│                    │  /customers/:id │  │
│                    │  / (UI)         │  │
│                    └─────────────────┘  │
└─────────────────────────────────────────┘
         ▲
         │  browser / curl / downstream tool
The db container runs init.sql on first start to create the schema and seed data. The API reads credentials from environment variables injected via .env. No reverse proxy, no separate static file server, no additional services.

What it makes easy

docker compose up starts exactly two services. Startup sequence is simple: db comes up first with a healthcheck, api waits on it.
One codebase, one container to build, one place to look when something breaks.
The UI and the API share the same origin — no CORS configuration needed. The browser talks to localhost:8000 for both the page and the API calls.
Serving a static file from FastAPI is one line: StaticFiles mount or a single FileResponse route. Nothing to configure.
Environment variable injection is straightforward — one .env file, one service consuming it.
Testing the full stack end-to-end is simple: one container to exec into, one port to hit.


What it makes hard

The API and the UI share a process. If the FastAPI worker crashes, the UI is also unavailable. For a read-only internal tool this is low consequence, but it's worth naming.
Serving static files from FastAPI is not wrong, but it conflates two responsibilities in one process. Future separation (if the UI ever needs to be independently deployed) requires more surgery than if they had been separate from the start.
Log output mixes API request logs and static file serve logs. Not a problem at this scale but can make log reading noisier.
If the UI grows complex (multi-page, assets), managing static file routing inside FastAPI becomes more involved than a dedicated server would be.


Constraints satisfied
ConstraintSatisfied?docker compose up only, .env the only setup
✅ Two services, no manual stepsNo external service calls
✅ Nothing leaves the container networkUI served by same container stack
✅ Served directly by the api containerRead-only, no write endpoints
✅ Enforced by what routes existFixed stack (Compose, Postgres, FastAPI, psycopg2, vanilla JS)
✅ No additions No ORM
✅ psycopg2 directlyNo frontend framework
✅ Plain HTML/JS fileAPI key auth on endpoints
✅ FastAPI dependency injectionInternal errors must not surface to callers
✅ Error handling is a FastAPI concern, same codeService startup order enforced
✅ Compose depends_on with condition: service_healthyNo constraints violated or left partially satisfied.

What you'd be giving up compared to the others

Compared to B: no separation between the static file serving layer and the application layer. If you ever want to cache the UI independently, put a CDN in front of just the UI, or deploy them to different hosts, you'd be starting from scratch.
Compared to C: no explicit application layer between the router and the database call. Everything lives in one file or one module — which is fine at this scale, but means there's no forced seam between routing, auth, and data access.



Candidate Architecture B — Two Containers Plus a Reverse Proxy
What it is
Three services in Docker Compose: db (Postgres), api (FastAPI, API only — no UI serving), and nginx (serves the static UI and proxies API calls). The browser talks only to nginx on port 80. Nginx serves index.html directly and forwards /api/* requests to the FastAPI container on its internal port. FastAPI never exposes a port to the host directly.
┌──────────────────────────────────────────────────────┐
│  Docker Compose                                      │
│                                                      │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │ db       │◄──│ api          │◄──│ nginx       │  │
│  │ Postgres │   │ FastAPI      │   │ :80         │  │
│  │ :5432    │   │ :8000        │   │  /  → UI    │  │
│  └──────────┘   │ /customers   │   │  /api → api │  │
│                 │ /health      │   └─────────────┘  │
│                 └──────────────┘                     │
└──────────────────────────────────────────────────────┘
         ▲
         │  browser / curl
The UI's JavaScript makes requests to /api/customers/{id} — same origin, no CORS. Nginx handles the routing split. FastAPI is network-isolated to the Docker internal network.

What it makes easy

Clear separation: nginx owns static serving, FastAPI owns API logic. Each does one thing.
FastAPI is not exposed to the host at all — only nginx is. This is a cleaner network boundary.
Nginx is extremely well understood for static file serving and proxying. Its behaviour is predictable and its configuration is stable.
If the UI grows, nginx handles it without touching FastAPI code.
Caching headers, compression, and request buffering at the nginx layer come essentially for free.


What it makes hard

Three services to start, three to debug when something fails. The startup dependency chain is now: db healthy → api healthy → nginx starts. More moving parts.
An nginx configuration file must be written and maintained. For a simple proxy this is small, but it's an additional artifact that can contain bugs.
The brief specifies "no manual setup steps beyond .env." An nginx config file that is wrong will fail silently or with confusing errors — debugging nginx config is not the same skill set as debugging Python.
The stack is more complex than the problem requires. This is a read-only internal lookup tool. The operational overhead of nginx is disproportionate.
docker compose up now starts three processes with three logs to monitor. For a solo practitioner exercise this adds noise.
Partial constraint concern: The brief says "UI must be served by the same container stack." This is satisfied — nginx is in the stack. But nginx is not in the fixed stack as listed. The brief lists Docker Compose, Postgres, FastAPI, psycopg2, vanilla JS. Nginx is not listed. Adding it means adding a technology outside the stated fixed stack.


Constraints satisfied
ConstraintSatisfied?docker compose up only, .env the only setup✅ With a committed nginx.confNo external service calls✅UI served by same container stack✅ nginx is in the Compose stackRead-only, no write endpoints✅Fixed stack⚠️ nginx is not in the stated fixed stackNo ORM✅No frontend framework✅API key auth on endpoints✅ Could be at nginx or FastAPI layerInternal errors must not surface✅ nginx adds an additional bufferService startup order enforced✅ But three-stage chain is more fragile
One constraint is flagged: nginx sits outside the specified fixed stack. It's additive, not substitutive — but it's an addition nonetheless.

What you'd be giving up compared to the others

Compared to A: simplicity. You add a third service, a new configuration file, and a new debugging surface for no functional gain at this scale.
Compared to C: nginx knows nothing about the application. If the API auth dependency is misconfigured, nginx won't catch it. Error handling is still entirely FastAPI's problem — nginx just passes responses through.



Candidate Architecture C — Single Container, Explicit Layered Module Structure
What it is
Structurally identical to A — two Docker Compose services, db and api — but the FastAPI application is explicitly structured as distinct internal layers: a router layer (route definitions only), an auth layer (dependency, separate module), a data access layer (all psycopg2 calls, separate module), and a response schema layer (Pydantic models defining the output contract). The UI is served by FastAPI exactly as in A. The distinction from A is architectural discipline inside the single container, not a change to the runtime topology.
┌─────────────────────────────────────────────────┐
│  Docker Compose                                 │
│                                                 │
│  ┌──────────┐      ┌──────────────────────────┐ │
│  │ db       │◄─────│ api                      │ │
│  │ Postgres │      │  router.py               │ │
│  │ :5432    │      │    └─ auth.py (dep)       │ │
│  └──────────┘      │    └─ db.py (data access) │ │
│                    │    └─ schemas.py           │ │
│                    │  static/index.html         │ │
│                    └──────────────────────────  ┘ │
└─────────────────────────────────────────────────┘
         ▲
         │  browser / curl / downstream tool
Each invariant maps to exactly one module. INV-06 (key never in response) lives entirely in auth.py. INV-03 (no writes, parameterised queries) lives entirely in db.py. Reviewing an invariant means reading one file.

What it makes easy

Invariant-to-code traceability is explicit. During the code review step of PBVI, you know exactly where to look.
auth.py can be tested in isolation — import it, call verify_api_key, assert the behaviour. No need to spin up the full application to test auth logic.
db.py can be reviewed independently for SQL safety. A reviewer looking for string concatenation in SQL queries reads one file, not all of main.py.
The response schema is enforced by Pydantic at the serialisation boundary — not by convention. If the database returns a column the schema doesn't expect, it's dropped. If a required field is missing, it errors explicitly.
Adding a second endpoint in the future (if scope ever grows) means adding a route to the router — the auth and data access layers don't change.
docker compose up is still two services. Operational simplicity of A is fully preserved.


What it makes hard

More files to create upfront for a small system. For three routes and one database query, a five-module structure can feel like over-engineering.
The module boundaries must be enforced by discipline, not by the runtime. Nothing stops a future developer from importing the database function directly into the router, bypassing the intended layer.
Pydantic schema definition adds a small amount of boilerplate that A doesn't have. It's minimal, but it's present.
If a developer is unfamiliar with FastAPI's dependency injection, the auth layer pattern (a function used as a Depends() argument) can be non-obvious to read.


Constraints satisfied
ConstraintSatisfied?docker compose up only, .env the only setup✅ Same as A — two servicesNo external service calls✅UI served by same container stack✅ Served by api containerRead-only, no write endpoints✅ Enforced in router layerFixed stack✅ No additions beyond what A usesNo ORM✅ psycopg2 in db.py onlyNo frontend framework✅API key auth on endpoints✅ Explicit dependency in auth.pyInternal errors must not surface✅ Error boundary in db.py, not scatteredService startup order enforced✅ Same Compose depends_on as A
All constraints satisfied. No flags.

What you'd be giving up compared to the others

Compared to A: slightly more upfront structure. If the system is genuinely throwaway after this exercise, the layering buys less.
Compared to B: no network-level separation between UI serving and API. A nginx misconfiguration can't take down the API here — but equally, a FastAPI crash takes both down. The tradeoff is operational simplicity vs. process isolation.


Summary Comparison
A — Single container, flatB — Three containers, nginxC — Single container, layeredServices in Compose232Stack additionsNonenginx (not in brief)NoneInternal structureFlat, one moduleFlat FastAPI + nginxExplicit layersInvariant traceabilityBy conventionBy conventionBy moduleOperational complexityLowMediumLowTestability of auth in isolationHarderHarderStraightforwardConstraint violationsNonenginx outside fixed stackNoneEffort to startLowestHigherLow