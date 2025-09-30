from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from core.errors import (
    AccountNotFoundError,
    DuplicateIdempotencyKeyError,
    InsufficientFundsError,
)

from models.schemas import (
    AccountCreate,
    AccountResponse,
    LedgerEntryResponse,
    MoneyMovementRequest,
    StatementResponse,
    TransferRequest,
)

@dataclass
class _AccountRecord:
    id: UUID
    owner_name: str
    created_at: datetime
    balance: int

@dataclass
class _LedgerEntryRecord:
    id: UUID
    ts: datetime
    account_id: UUID
    amount: int
    type: str
    ref: Optional[str] = None

@dataclass
class _IdempotencyRecord:
    request_signature: Tuple
    response_payload: AccountResponse | StatementResponse

class LedgerService:
    def __init__(self) -> None:
        self._accounts: Dict[UUID, _AccountRecord] = {}
        self._entries: Dict[UUID, List[_LedgerEntryRecord]] = {}
        self._idempotency: Dict[Tuple[str, str], _IdempotencyRecord] = {}

    def _get_account(self, account_id: UUID) -> _AccountRecord:
        try:
            return self._accounts[account_id]
        except KeyError as exc:
            raise AccountNotFoundError(f"Account {account_id} not found") from exc
    
    def _record_idempotent(
        self,
        route: str,
        idempotency_key: str,
        request_signature: Tuple,
        response_payload: AccountResponse | StatementResponse,
    ) -> None:
        self._idempotency[(route, idempotency_key)] = _IdempotencyRecord(
            request_signature=request_signature,
            response_payload=response_payload,
        )