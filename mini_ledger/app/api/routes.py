from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from ..core.dependencies import get_ledger_service
from ..models import (
    AccountCreate,
    AccountResponse,
    MoneyMovementRequest,
    StatementResponse,
    TransferRequest,
)
from ..services import LedgerService


router = APIRouter(prefix="/accounts", tags=["accounts"])

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
    return service.get_account(account_id)

@router.post("/{account_id}/deposit", response_model=AccountResponse)
def deposit(
    account_id: UUID,
    payload: MoneyMovementRequest,
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str = Header(..., convert_underscores=False, alias="Idempotency-Key"),
) -> AccountResponse:
    return service.deposit(account_id, payload, idempotency_key)

@router.post("/{account_id}/withdraw", response_model=AccountResponse)
def withdraw(
    account_id: UUID,
    payload: MoneyMovementRequest,
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str = Header(..., convert_underscores=False, alias="Idempotency-Key"),
) -> AccountResponse:
    return service.withdraw(account_id, payload, idempotency_key)

@router.get("/{account_id}/statement", response_model=StatementResponse)
def get_statement(
    account_id: UUID,
    limit: int = 50,
    cursor: str | None = None,
    service: LedgerService = Depends(get_ledger_service),
) -> StatementResponse:
    return service.get_statement(account_id, limit=limit, cursor=cursor)

transfer_router = APIRouter(prefix="/transfers", tags=["transfers"])

@transfer_router.post("", response_model=dict)
def create_transfer(
    payload: TransferRequest,
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str = Header(..., convert_underscores=False, alias="Idempotency-Key"),
) -> dict:
    source, dest = service.transfer(payload, idempotency_key)
    return {"source": source, "dest": dest}

__all__ = ["router", "transfer_router"]
