from fastapi import FastAPI

app = FastAPI(title="Mini Ledger API")

@app.get("/health")
def read_health():
    return {"status": "ok"}