from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from ..core.errors import (
    AccountNotFoundError,
    DuplicateIdempotencyKeyError,
    InsufficientFundsError,
)

from ..models import (
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
    response_payload: object

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
        response_payload: object,
    ) -> None:
        self._idempotency[(route, idempotency_key)] = _IdempotencyRecord(
            request_signature=request_signature,
            response_payload=response_payload,
        )
    
    def _check_idempotency(
        self,
        route: str,
        idempotency_key: str,
        request_signature: Tuple,
    ) -> Optional[object]:
        record = self._idempotency.get((route, idempotency_key))
        if record is None:
            return None
        
        if record.request_signature != request_signature:
            raise DuplicateIdempotencyKeyError(
                "Idempotency key was previously used with different parameters"
            )
        
        return record.response_payload  # Returning cached payload keeps repeated calls idempotent

    def create_account(self, payload: AccountCreate) -> AccountResponse:
        account_id = uuid4()
        now = datetime.utcnow()

        record = _AccountRecord(
            id = account_id,
            owner_name = payload.owner_name,
            created_at=now,
            balance=0,
        )
        self._accounts[account_id] = record
        self._entries[account_id] = []

        return AccountResponse(
            id=record.id,
            owner_name=record.owner_name,
            created_at=record.created_at,
            balance=record.balance,
        )
    
    def _append_entry(
        self,
        account_id: UUID,
        amount: int,
        entry_type: str,
        ref: Optional[str] = None,
    ) -> _LedgerEntryRecord:
        entry = _LedgerEntryRecord(
            id = uuid4(),
            ts = datetime.utcnow(),
            account_id = account_id,
            amount = amount,
            type = entry_type,
            ref = ref,
        )
        self._entries[account_id].append(entry)
        return entry
    
    def deposit(
        self,
        account_id: UUID,
        payload: MoneyMovementRequest,
        idempotency_key: str,
    ) -> AccountResponse:
        request_signature = ("deposit", account_id, payload.amount, payload.memo)
        cached = self._check_idempotency("deposit", idempotency_key, request_signature)
        if isinstance(cached, AccountResponse):
            return cached
        
        account = self._get_account(account_id)
        account.balance += payload.amount
        self._append_entry(account_id, payload.amount, "CREDIT", payload.memo)

        response = AccountResponse(
            id = account.id,
            owner_name = account.owner_name,
            created_at = account.created_at,
            balance = account.balance,
        )
        self._record_idempotent("deposit", idempotency_key, request_signature, response)
        return response
    
    def withdraw(
        self,
        account_id: UUID,
        payload: MoneyMovementRequest,
        idempotency_key: str,
    ) -> AccountResponse:
        request_signature = ("withdraw", account_id, payload.amount, payload.memo)
        cached = self._check_idempotency("withdraw", idempotency_key, request_signature)
        if isinstance(cached, AccountResponse):
            return cached
        
        account = self._get_account(account_id)
        if account.balance < payload.amount:
            raise InsufficientFundsError("Insufficient funds for withdrawal")
        
        account.balance -= payload.amount
        self._append_entry(account_id, payload.amount * -1, "DEBIT", payload.memo)

        response = AccountResponse(
            id = account.id,
            owner_name = account.owner_name,
            created_at = account.created_at,
            balance = account.balance,
        )
        self._record_idempotent("withdraw", idempotency_key, request_signature, response)
        return response
    
    def transfer(
        self,
        payload: TransferRequest,
        idempotency_key: str,
    ) -> Tuple[AccountResponse, AccountResponse]:
        request_signature = (
            "transfer",
            payload.source_account_id,
            payload.dest_account_id,
            payload.amount,
            payload.memo,
        )
        cached = self._check_idempotency("transfer", idempotency_key, request_signature)
        if cached:
            if isinstance(cached, dict) and "source" in cached and "dest" in cached:
                source_cached = cached["source"]
                dest_cached = cached["dest"]
                if isinstance(source_cached, AccountResponse) and isinstance(dest_cached, AccountResponse):
                    return source_cached, dest_cached
            raise DuplicateIdempotencyKeyError(
                "Transfer idempotency key cannot be reused with mismatched payload"
            )
        
        if payload.source_account_id == payload.dest_account_id:
            raise ValueError("Cannot transfer to the same account")
        
        source = self._get_account(payload.source_account_id)
        dest = self._get_account(payload.dest_account_id)

        if source.balance < payload.amount:
            raise InsufficientFundsError("Insufficient funds for transfer")
        
        source.balance -= payload.amount
        dest.balance += payload.amount

        debit = self._append_entry(
            payload.source_account_id,
            payload.amount * -1,
            "DEBIT",
            payload.memo,
        )

        credit = self._append_entry(
            payload.dest_account_id,
            payload.amount,
            "CREDIT",
            payload.memo,
        )

        source_response = AccountResponse(
            id = source.id,
            owner_name = source.owner_name,
            created_at = source.created_at,
            balance = source.balance,
        )

        dest_response = AccountResponse(
            id = dest.id,
            owner_name = dest.owner_name,
            created_at = dest.created_at,
            balance = dest.balance,
        )

        self._record_idempotent(
            "transfer",
            idempotency_key,
            request_signature,
            {"source": source_response, "dest": dest_response},
        )

        return source_response, dest_response

    
    def get_account(self, account_id: UUID) -> AccountResponse:
        account = self._get_account(account_id)
        return AccountResponse(
            id = account.id,
            owner_name=account.owner_name,
            created_at=account.created_at,
            balance=account.balance,
        )

    def get_statement(
        self,
        account_id: UUID,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> StatementResponse:
        self._get_account(account_id) # ensure account exists

        entries = self._entries[account_id]
        entries_sorted = sorted(entries, key=lambda e: e.ts, reverse=True)

        start_index = 0
        if cursor:
            try:
                cursor_ts = datetime.fromisoformat(cursor)
            except ValueError as exc:
                raise ValueError("Invalid cursor") from exc
            for idx, entry in enumerate(entries_sorted):
                if entry.ts.isoformat() == cursor_ts.isoformat():
                    start_index = idx + 1
                    break
        
        slice_entries = entries_sorted[start_index : start_index + limit]
        next_cursor = None
        if start_index + limit < len(entries_sorted):
            next_cursor = slice_entries[-1].ts.isoformat()
        
        items = [
            LedgerEntryResponse(
                id = entry.id,
                ts = entry.ts,
                account_id = entry.account_id,
                amount = entry.amount,
                type = entry.type,
                ref = entry.ref,
            )
            for entry in slice_entries
        ]

        return StatementResponse(items = items, next_cursor = next_cursor)
    
