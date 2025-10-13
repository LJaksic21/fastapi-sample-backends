from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from ..core.dependencies import get_ledger_service
from ..core.errors import (
    AccountNotFoundError,
    DuplicateIdempotencyKeyError,
    InsufficientFundsError,
)
from ..models import (
    AccountCreate,
    AccountResponse,
    MoneyMovementRequest,
    StatementResponse,
    TransferRequest,
)
from ..services import LedgerService

router = APIRouter(prefix="/accounts", tags=["accounts"])

def handle_service_errors(error: Exception) -> None:
    if isinstance(error, AccountNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, InsufficientFundsError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, DuplicateIdempotencyKeyError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    raise error

@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    service: LedgerService = Depends(get_ledger_service),
) -> AccountResponse:
    return service.create_account(payload)

@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: UUID,
    service: LedgerService = Depends(get_ledger_service),
) -> AccountResponse:
    try:
        return service.get_account(account_id)
    except Exception as exc: # catch service-level errors
        handle_service_errors(exc)

@router.post("/{account_id}/deposit", response_model=AccountResponse)
def deposit(
    account_id: UUID,
    payload: MoneyMovementRequest,
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str = Header(..., convert_underscores=False, alias="Idempotency-Key"),
) -> AccountResponse:
    try:
        return service.deposit(account_id, payload, idempotency_key)
    except Exception as exc:
        handle_service_errors(exc)

@router.get("/{account_id}/statement", response_model=StatementResponse)
def get_statement(
    account_id: UUID,
    limit: int = 50,
    cursor: str | None = None,
    service: LedgerService = Depends(get_ledger_service),
) -> StatementResponse:
    try:
        return service.get_statement(account_id, limit=limit, cursor=cursor)
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        handle_service_errors(exc)

transfer_router = APIRouter(prefix="/transfers", tags=["transfers"])

@transfer_router.post("", response_model=dict)
def create_transfer(
    payload: TransferRequest,
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str = Header(..., convert_underscores=False, alias="Idempotency-Key"),
) -> dict:
    try:
        source, dest = service.transfer(payload, idempotency_key)
        return {"source": source, "dest": dest}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        handle_service_errors(exc)

__all__ = ["router", "transfer_router"]