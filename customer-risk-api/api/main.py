import os

import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()


async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    valid_key = os.environ.get("API_KEY")
    if not api_key or api_key != valid_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_db_connection():
    try:
        return psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(content="UI coming soon")


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str, api_key: str = Depends(verify_api_key)):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT customer_id, risk_tier, risk_factors FROM customer_risk_profiles WHERE customer_id = %s",
            (customer_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {"customer_id": row[0], "risk_tier": row[1], "risk_factors": row[2]}
    finally:
        conn.close()
