from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(content="UI coming soon")


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    return {"message": "placeholder"}
