from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional, Tuple
from uuid import UUID

from sqlmodel import Session

from ..core.errors import (
    AccountNotFoundError,
    DuplicateIdempotencyKeyError,
    InsufficientFundsError,
)
from ..models import (
    AccountCreate,
    AccountModel,
    AccountResponse,
    LedgerEntryResponse,
    MoneyMovementRequest,
    StatementResponse,
    TransferRequest,
)
from .repository import LedgerRepository


logger = logging.getLogger(__name__)


class LedgerService:
    def __init__(
        self,
        session: Session,
        repository: Optional[LedgerRepository] = None,
    ) -> None:
        self.session = session
        self.repository = repository or LedgerRepository(session)

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value

    def _serialize(self, payload: Any) -> str:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(mode="json")
        elif hasattr(payload, "dict"):
            data = payload.dict()
        else:
            data = payload
        return json.dumps(data, default=self._json_default, sort_keys=True)

    def _encode_signature(self, signature: Tuple[Any, ...]) -> str:
        return json.dumps(signature, default=self._json_default, sort_keys=True)

    def _deserialize_account(self, payload: str) -> AccountResponse:
        data = json.loads(payload)
        return AccountResponse.model_validate(data)

    def _deserialize_transfer(self, payload: str) -> Tuple[AccountResponse, AccountResponse]:
        data = json.loads(payload)
        return (
            AccountResponse.model_validate(data["source"]),
            AccountResponse.model_validate(data["dest"]),
        )

    def _get_account(self, account_id: UUID) -> AccountModel:
        account = self.repository.get_account(account_id)
        if account is None:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _check_idempotency(
        self,
        route: str,
        idempotency_key: str,
        request_signature: Tuple[Any, ...],
    ) -> Optional[str]:
        record = self.repository.fetch_idempotency(route, idempotency_key)
        if record is None:
            return None

        signature = self._encode_signature(request_signature)
        if record.request_signature != signature:
            raise DuplicateIdempotencyKeyError(
                "Idempotency key was previously used with different parameters"
            )

        return record.response_payload

    def _record_idempotent(
        self,
        route: str,
        idempotency_key: str,
        request_signature: Tuple[Any, ...],
        response_payload: Any,
    ) -> None:
        signature = self._encode_signature(request_signature)
        serialized_payload = self._serialize(response_payload)
        self.repository.save_idempotency(
            route=route,
            key=idempotency_key,
            signature=signature,
            payload=serialized_payload,
        )

    def _account_to_response(self, account: AccountModel) -> AccountResponse:
        return AccountResponse(
            id=account.id,
            owner_name=account.owner_name,
            created_at=account.created_at,
            balance=account.balance,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_account(self, payload: AccountCreate) -> AccountResponse:
        account = self.repository.add_account(payload.owner_name)
        self.session.commit()
        logger.info(
            "account.created",
            extra={"account_id": str(account.id), "owner_name": account.owner_name},
        )
        return self._account_to_response(account)

    def deposit(
        self,
        account_id: UUID,
        payload: MoneyMovementRequest,
        idempotency_key: str,
    ) -> AccountResponse:
        request_signature = ("deposit", str(account_id), payload.amount, payload.memo)
        cached = self._check_idempotency("deposit", idempotency_key, request_signature)
        if cached is not None:
            logger.info(
                "idempotent.deposit.hit",
                extra={"account_id": str(account_id), "idempotency_key": idempotency_key},
            )
            return self._deserialize_account(cached)

        account = self._get_account(account_id)
        account.balance += payload.amount

        self.repository.add_entry(
            account_id=account_id,
            amount=payload.amount,
            entry_type="CREDIT",
            memo=payload.memo,
        )

        response = self._account_to_response(account)
        self._record_idempotent("deposit", idempotency_key, request_signature, response)
        self.session.commit()
        self.session.refresh(account)
        logger.info(
            "account.deposit",
            extra={
                "account_id": str(account_id),
                "amount": payload.amount,
                "balance": account.balance,
            },
        )
        return self._account_to_response(account)

    def withdraw(
        self,
        account_id: UUID,
        payload: MoneyMovementRequest,
        idempotency_key: str,
    ) -> AccountResponse:
        request_signature = ("withdraw", str(account_id), payload.amount, payload.memo)
        cached = self._check_idempotency("withdraw", idempotency_key, request_signature)
        if cached is not None:
            logger.info(
                "idempotent.withdraw.hit",
                extra={"account_id": str(account_id), "idempotency_key": idempotency_key},
            )
            return self._deserialize_account(cached)

        account = self._get_account(account_id)
        if account.balance < payload.amount:
            raise InsufficientFundsError("Insufficient funds for withdrawal")

        account.balance -= payload.amount

        self.repository.add_entry(
            account_id=account_id,
            amount=-payload.amount,
            entry_type="DEBIT",
            memo=payload.memo,
        )

        response = self._account_to_response(account)
        self._record_idempotent("withdraw", idempotency_key, request_signature, response)
        self.session.commit()
        self.session.refresh(account)
        logger.info(
            "account.withdraw",
            extra={
                "account_id": str(account_id),
                "amount": payload.amount,
                "balance": account.balance,
            },
        )
        return self._account_to_response(account)

    def transfer(
        self,
        payload: TransferRequest,
        idempotency_key: str,
    ) -> Tuple[AccountResponse, AccountResponse]:
        request_signature = (
            "transfer",
            str(payload.source_account_id),
            str(payload.dest_account_id),
            payload.amount,
            payload.memo,
        )
        cached = self._check_idempotency("transfer", idempotency_key, request_signature)
        if cached is not None:
            logger.info(
                "idempotent.transfer.hit",
                extra={
                    "source_account_id": str(payload.source_account_id),
                    "dest_account_id": str(payload.dest_account_id),
                    "idempotency_key": idempotency_key,
                },
            )
            return self._deserialize_transfer(cached)

        if payload.source_account_id == payload.dest_account_id:
            raise ValueError("Cannot transfer to the same account")

        source = self._get_account(payload.source_account_id)
        dest = self._get_account(payload.dest_account_id)

        if source.balance < payload.amount:
            raise InsufficientFundsError("Insufficient funds for transfer")

        source.balance -= payload.amount
        dest.balance += payload.amount

        self.repository.add_entry(
            account_id=payload.source_account_id,
            amount=-payload.amount,
            entry_type="DEBIT",
            memo=payload.memo,
        )
        self.repository.add_entry(
            account_id=payload.dest_account_id,
            amount=payload.amount,
            entry_type="CREDIT",
            memo=payload.memo,
        )

        source_response = self._account_to_response(source)
        dest_response = self._account_to_response(dest)
        cached_payload = {
            "source": source_response.model_dump(mode="json"),
            "dest": dest_response.model_dump(mode="json"),
        }
        self._record_idempotent(
            "transfer",
            idempotency_key,
            request_signature,
            cached_payload,
        )

        self.session.commit()
        self.session.refresh(source)
        self.session.refresh(dest)
        logger.info(
            "account.transfer",
            extra={
                "source_account_id": str(payload.source_account_id),
                "dest_account_id": str(payload.dest_account_id),
                "amount": payload.amount,
            },
        )
        return self._account_to_response(source), self._account_to_response(dest)

    def get_account(self, account_id: UUID) -> AccountResponse:
        account = self._get_account(account_id)
        return self._account_to_response(account)

    def get_statement(
        self,
        account_id: UUID,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> StatementResponse:
        self._get_account(account_id)

        entries = self.repository.list_entries(account_id)

        start_index = 0
        if cursor:
            try:
                cursor_ts = datetime.fromisoformat(cursor)
            except ValueError as exc:
                raise ValueError("Invalid cursor") from exc
            for idx, entry in enumerate(entries):
                if entry.ts.isoformat() == cursor_ts.isoformat():
                    start_index = idx + 1
                    break

        slice_entries = entries[start_index : start_index + limit]
        next_cursor = None
        if start_index + limit < len(entries):
            next_cursor = slice_entries[-1].ts.isoformat()

        items = [
            LedgerEntryResponse(
                id=entry.id,
                ts=entry.ts,
                account_id=entry.account_id,
                amount=entry.amount,
                type=entry.type,
                ref=entry.ref,
            )
            for entry in slice_entries
        ]

        return StatementResponse(items=items, next_cursor=next_cursor)
