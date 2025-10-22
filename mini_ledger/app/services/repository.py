from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from ..models import AccountModel, IdempotencyRecordModel, LedgerEntryModel


class LedgerRepository:
    """Thin data access layer around the SQLModel session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # Account operations -------------------------------------------------
    def add_account(self, owner_name: str) -> AccountModel:
        account = AccountModel(owner_name=owner_name)
        self.session.add(account)
        self.session.flush()
        self.session.refresh(account)
        return account

    def get_account(self, account_id: UUID) -> Optional[AccountModel]:
        return self.session.get(AccountModel, account_id)

    # Ledger entries -----------------------------------------------------
    def add_entry(
        self,
        *,
        account_id: UUID,
        amount: int,
        entry_type: str,
        memo: Optional[str],
    ) -> LedgerEntryModel:
        entry = LedgerEntryModel(
            account_id=account_id,
            amount=amount,
            type=entry_type,
            ref=memo,
        )
        self.session.add(entry)
        self.session.flush()
        self.session.refresh(entry)
        return entry

    def list_entries(self, account_id: UUID) -> list[LedgerEntryModel]:
        stmt = (
            select(LedgerEntryModel)
            .where(LedgerEntryModel.account_id == account_id)
            .order_by(LedgerEntryModel.ts.desc())
        )
        return list(self.session.exec(stmt))

    # Idempotency store --------------------------------------------------
    def fetch_idempotency(
        self, route: str, key: str
    ) -> Optional[IdempotencyRecordModel]:
        stmt = (
            select(IdempotencyRecordModel)
            .where(IdempotencyRecordModel.route == route)
            .where(IdempotencyRecordModel.key == key)
        )
        return self.session.exec(stmt).first()

    def save_idempotency(
        self,
        *,
        route: str,
        key: str,
        signature: str,
        payload: str,
    ) -> None:
        record = IdempotencyRecordModel(
            route=route,
            key=key,
            request_signature=signature,
            response_payload=payload,
        )
        self.session.add(record)
