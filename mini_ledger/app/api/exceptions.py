from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..core.errors import (
    AccountNotFoundError,
    DuplicateIdempotencyKeyError,
    InsufficientFundsError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AccountNotFoundError)
    async def account_not_found_handler(
        request: Request, exc: AccountNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InsufficientFundsError)
    async def insufficient_funds_handler(
        request: Request, exc: InsufficientFundsError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(DuplicateIdempotencyKeyError)
    async def duplicate_idempotency_handler(
        request: Request, exc: DuplicateIdempotencyKeyError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
