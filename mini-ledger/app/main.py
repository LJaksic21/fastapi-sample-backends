from fastapi import FastAPI

from .api.routes import router as accounts_router, transfer_router

app = FastAPI(title="Mini Ledger API")

app.include_router(accounts_router)
app.include_router(transfer_router)

@app.get("/health")
def read_health() -> dict[str, str]:
    return {"status": "ok"}