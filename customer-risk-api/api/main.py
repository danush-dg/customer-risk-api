import os

import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Customer Risk Lookup</title>
<style>
  body { font-family: monospace; max-width: 600px; margin: 40px auto; padding: 0 20px; }
  label { display: block; margin-top: 12px; font-size: 0.9em; }
  input { width: 100%; padding: 6px; box-sizing: border-box; margin-top: 4px; font-family: monospace; }
  button { margin-top: 16px; padding: 8px 20px; cursor: pointer; }
  #result { margin-top: 24px; padding: 12px; border: 1px solid #ccc; white-space: pre-wrap; min-height: 60px; }
</style>
</head>
<body>
<h1>Customer Risk Lookup</h1>
<label>API Key
  <input type="password" id="apiKey" placeholder="X-API-Key">
</label>
<label>Customer ID
  <input type="text" id="customerId" placeholder="CUST-001">
</label>
<button onclick="lookup()">Look Up</button>
<div id="result"></div>
<script>
async function lookup() {
  var id = document.getElementById('customerId').value.trim();
  var key = document.getElementById('apiKey').value;
  var out = document.getElementById('result');
  if (!id) { out.textContent = 'Enter a customer ID.'; return; }
  try {
    var res = await fetch('/customers/' + encodeURIComponent(id), {
      headers: { 'X-API-Key': key }
    });
    var data = await res.json();
    if (data.detail) {
      out.textContent = data.detail;
    } else {
      out.textContent =
        'customer_id: ' + data.customer_id + '\\n' +
        'risk_tier: ' + data.risk_tier + '\\n' +
        'risk_factors:\\n' + data.risk_factors.map(function(f) { return '  - ' + f; }).join('\\n');
    }
  } catch (e) {
    out.textContent = 'Request failed.';
  }
}
document.getElementById('customerId').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') lookup();
});
</script>
</body>
</html>"""

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
    return HTMLResponse(content=_HTML)


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
