1. Problem Statement
The core problem is uncontrolled, unauditable access to sensitive financial data. Risk analysts are going directly to the database — which means access control is bypassed, query quality is inconsistent, and there's no defined contract for what "risk tier" means in a response. The client needs a stable, authenticated interface that sits between consumers and the data so that who asked, what they received, and in what shape it arrived can all be reasoned about — even if auditing isn't explicitly in scope here.
The secondary problem is operational fragility. Ad-hoc SQL is slow and error-prone not just because analysts write bad queries, but because there's no enforcement that they're querying the right table, interpreting tiers consistently, or handling missing customers correctly. The API enforces that contract.

2. Constraints
Stated:
- Read-only. No write endpoints, no update paths.
- No external network calls. Fully local.
- Single .env file is the only setup step. docker compose up must do everything else.
- UI must be served from within the container stack — not separately hosted.
- Fixed stack: Docker Compose, Postgres 15, FastAPI/Python 3.11, psycopg2, vanilla HTML/JS. No substitutions.
- No ORM. psycopg2 directly.
- No frontend framework.

Implied but not stated:

- The API key must never appear in a response body or log output. Authentication errors must use a static message, not echo the submitted key or describe why it failed.
- Internal error details must never surface to callers. A database connection failure, a malformed query, or a missing environment variable must return a generic 5xx — not a traceback or connection string fragment.
- The database schema must be immutable at runtime. No triggers, no stored procedures with side effects, nothing that allows a read to cause a write.
- The seed data is the source of truth. The system does not compute or derive risk — what's in the database is what gets returned, verbatim. Any transformation in the API layer would violate this.
- The UI must not interpret or reformat API output. If the API returns "HIGH", the UI displays "HIGH" — it does not map it to a colour, label, or description that could diverge from the actual value.
- Service startup order must be enforced. The API container must not accept connections until the database is healthy. An API that starts before the DB is ready and serves errors is operationally misleading.
- The .env file must not be committed. Only .env.example should exist in version control.

Vague — needs resolution:

"All endpoints" for auth enforcement: The /health endpoint is almost certainly needed for the Docker healthcheck. Does it require authentication? The brief doesn't say. If it does, the healthcheck breaks. If it doesn't, it becomes an unauthenticated information surface.
"A list of risk factors": The brief says the API returns "the list of risk factors that contributed to that tier." It does not specify what a risk factor looks like — is it a string? A structured object with a code and description? This affects the schema and the UI rendering.
"Clear 404 response": Clear to whom? The brief implies a JSON body, but doesn't specify the shape. The error body for 404 should match the error body for 401 in structure, or the UI must handle two different shapes.


3. Definition of Success
Success looks like this in concrete terms:

An operations staff member types a customer ID into the browser UI, clicks a button, and sees the correct tier and factors — without knowing SQL, without database credentials, and without writing any code.
A downstream tool can make an authenticated GET /customers/{id} call and receive a JSON response whose shape never changes regardless of which customer is queried or which tier they're in.
A request with a missing or wrong API key receives a 401 with a static message — every time, with no variation.
A request for a non-existent customer ID receives a 404 — not a 500, not an empty 200.
The entire stack starts cold from docker compose up on a machine with only Docker and a valid .env file, with no intervention.
The data returned is exactly what is in the database. No interpretation, no transformation.


4. Failure Modes
FM-1: The API becomes a write path under adversarial input.
The system is read-only, but if SQL queries are constructed with string formatting rather than parameterised queries, a crafted customer_id could execute arbitrary SQL — including writes. This is not a code bug; it's a design failure in how the data access layer is specified. The invariant must be: parameterised queries everywhere, enforced at the code review stage, not just tested.
FM-2: Authentication is present but not enforced on the right boundary.
A common failure: the auth dependency is written but attached to the wrong place, or not attached at all on one route, or bypassed by a middleware ordering issue. The result is a system that appears authenticated but allows unauthenticated access to data on a specific path. The API key check must be a dependency on the lookup endpoint, not a general middleware that can be silently skipped.
FM-3: Internal state leaks through error responses.
If the database goes down, if an environment variable is missing, or if psycopg2 throws an unhandled exception, the raw exception — potentially containing connection strings, table names, or stack traces — can reach the caller. This is not a rare edge case; it's a startup condition and a runtime condition. Every code path that touches the database must have an explicit error boundary.
FM-4: The UI diverges from the API.
If the UI transforms the API response — maps tier codes to display labels, reformats factors, or applies conditional logic — it becomes a second source of truth. When the database is updated, the API changes correctly but the UI still shows the old interpretation. The UI's job is to display what the API returns, not to interpret it.

5. Missing Information

The shape of a risk factor. Is it a plain string ("PEP_STATUS")? A structured object ({"code": "PEP_STATUS", "description": "Politically Exposed Person"})?  This is the most consequential gap — it affects the database schema, the API response contract, and what the UI needs to render.
Authentication on /health. The healthcheck endpoint is implied by the Docker dependency setup. Does it require the API key? If yes, the Compose healthcheck configuration is more complex. If no, it must be explicitly excluded from auth enforcement and that exclusion documented.
Error response shape for 4xx/5xx. The 404 and 401 cases need a defined JSON body. Without it, the UI must handle an undefined structure — which either fails silently or requires the UI to interpret error responses, which violates FM-4.
Customer ID format. Is customer_id a UUID? An integer? A prefixed string like CUST-001? This affects URL routing (path parameter validation), seed data design, and what the UI input field should accept or reject.
Seed data depth. "Representative" is undefined. How many customers? Are all three tiers required to have multiple records? This matters for invariant testing — if there's only one customer per tier, the test coverage is thin.