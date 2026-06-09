# Customer Risk API

## What it is

The Customer Risk API provides authenticated, read-only HTTP access to pre-assessed customer risk tier data stored in Postgres. Operations staff can query a customer's risk status by ID and receive a structured JSON response containing the customer ID, risk tier, and the factors that drove the assessment. The API does not compute or modify risk data — it surfaces what is already in the database.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- Git
- A `.env` file with valid credentials (see Setup)

## Setup

```bash
cp .env.example .env
# Edit .env — fill in POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and API_KEY
docker compose up -d
```

The API is ready when `docker compose ps` shows both `db` and `api` as running. Allow a few seconds for the database healthcheck to pass before making requests.

## Usage

**Health check (unauthenticated):**
```bash
curl http://localhost:8000/health
```
```json
{"status": "ok"}
```

**Customer lookup — found:**
```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-001
```
```json
{"customer_id": "CUST-001", "risk_tier": "LOW", "risk_factors": ["..."]}
```

**Customer lookup — not found:**
```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/customers/CUST-999
```
```json
{"detail": "Customer not found"}
```

**Unauthenticated request (expected 401):**
```bash
curl http://localhost:8000/customers/CUST-001
```
```json
{"detail": "Unauthorized"}
```

A browser UI is also available at `http://localhost:8000`.

## Teardown

```bash
docker compose down -v
```

> **Warning:** Omitting `-v` leaves the Postgres data volume in place. On the next `docker compose up`, the database initialisation script will not re-run, so seed data will not be reloaded. Always include `-v` when a clean state is required.

## Stack

| Component | Technology |
|---|---|
| Orchestration | Docker Compose |
| Database | Postgres 15 |
| API | FastAPI · Python 3.11 |
| Database driver | psycopg2-binary |
