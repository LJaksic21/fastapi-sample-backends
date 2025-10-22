import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.exceptions import register_exception_handlers
from .api.routes import router as accounts_router, transfer_router
from .core.config import get_settings
from .core.db import init_db

settings = get_settings()
logging.basicConfig(level=settings.log_level)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(accounts_router)
app.include_router(transfer_router)
register_exception_handlers(app)

@app.get("/health")
def read_health() -> dict[str, str]:
    return {"status": "ok"}