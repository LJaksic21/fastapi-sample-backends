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

