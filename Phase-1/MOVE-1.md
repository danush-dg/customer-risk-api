Problem Exploration — Customer Risk API

1. Problem Statement
The core problem is uncontrolled, unauditable access to sensitive financial data. Risk analysts are querying a production database directly — which means no access layer, no consistent output format, no authentication boundary, and no way to know who asked what. The risk tier data exists and is correct; the problem is that the only way to get at it bypasses every control that should exist around it. The client needs a defined interface that sits between the data and the people who need it, so that access is authenticated, output is consistent, and the database is no longer directly exposed to ad-hoc queries.

2. Constraints
Stated constraints:

No external service calls — the system is fully self-contained
Read-only — no write endpoints under any circumstances
Single-command startup — docker compose up with only an .env file required
UI served from the same container stack — no separate hosting
Stack is fixed — no substitutions permitted

Implied constraints not explicitly written:

The API key must never appear in any response body or log output — even in error responses. If the submitted key is wrong, the error must not echo it back
Internal errors must not surface to the caller — database exceptions, connection strings, and stack traces must be caught and returned as opaque error responses
The response schema must be stable — downstream tools depend on it. The field names, types, and structure cannot vary across calls or between customers
The database must be the single source of truth — the API must return exactly what the database holds, with no transformation, interpretation, or enrichment of risk tier or factors
The UI must not reinterpret API output — it renders what the API returns, not its own version of what the tier means
No credentials in the image or repository — the .env pattern implies credentials must never be hardcoded or committed
The system must be deterministic on cold start — the same docker compose up must produce the same data state every time, which means the seed data is static and idempotent

Vague areas flagged:

"All endpoints" — does this include /health? A health endpoint that bypasses auth is standard practice, but the brief doesn't say so explicitly
"Clear 404 response" — the structure of the 404 is not specified. Does it match the success response shape with null fields, or is it a different schema entirely?
"List of risk factors" — no schema defined. Is this an array of strings? Key-value pairs? What happens if the factors column is null or empty for a record?


3. Definition of Success
In concrete terms, success looks like this: an operations staff member opens a browser, enters a customer ID, and sees that customer's risk tier and contributing factors — without ever touching the database, without knowing SQL, and without any possibility of accidentally modifying data. The same lookup done twice returns the same result. A request with no API key is rejected before any data is accessed. A request for a customer that doesn't exist returns a clear not-found response, not silence or an error. The whole system starts from one command with no manual configuration beyond a provided .env file, and shuts down cleanly.

4. Failure Modes
F1 — Authentication bypass under edge cases
The auth layer is applied globally in intent, but if any route — health check, error handler, redirect — is registered before or outside the auth dependency, unauthenticated callers can reach it. The failure mode is not "no auth implemented" but "auth implemented inconsistently." The design must make it structurally impossible to add a route that isn't covered.
F2 — Data staleness or seed divergence
If the database initialisation is not idempotent, re-running docker compose up after a volume exists may produce a different data state than a clean start — or fail silently. Operations staff comparing results across environments or restarts could be working from different ground truth. The init process must be guaranteed to produce the same state on every cold start.
F3 — Internal error leakage under load or unexpected input
Any unhandled exception — database connection failure, malformed customer_id, unexpected column value — that propagates to the HTTP response will expose internal details: connection strings, table names, stack traces. The failure mode is not a crash, it's an information leak dressed as a crash. Every error path must be explicitly handled before it reaches the response layer.
F4 — Response schema drift between the API and the UI
If the UI makes assumptions about field names or value formats that differ from what the API actually returns, some customers will display correctly and others won't — or the display will break silently when an edge case (empty factors list, unexpected tier value) is encountered. The UI must be a pure renderer of API output with no independent interpretation logic.

5. Missing Information

Health endpoint authentication policy — is /health exempt from API key auth? This is a real design decision with operational implications and the brief doesn't address it
Customer ID format and validation — is customer_id a UUID, an integer, a prefixed string like CUST-001? What should happen if the format is syntactically invalid versus simply not found? Same 404, or a 400?
Risk factors schema — the brief mentions "factors that drove the assessment" but specifies no structure. This affects both the database schema and the response contract
API key rotation or multi-key support — the brief implies a single static key from .env. Is there ever a need to support more than one valid key simultaneously? Not in scope now, but it affects how the auth check is written
Error response schema — the 404 shape is unspecified. The 401 shape is unspecified. Do all error responses share a common structure, or are they independent?
Behaviour on empty factors — what should the API return if a customer record exists but has no associated risk factors? Empty array, null, or is this condition considered impossible given the seed data?