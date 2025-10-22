from __future__ import annotations
from datetime import datetime, UTC
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel

class Account(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    owner_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    balance: int = Field(default=0, ge=0)

class LedgerEntry(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    account_id: UUID = Field(foreign_key="account.id", index=True)
    amount: int
    type: str
    ref: Optional[str] = None

class IdempotencyRecord(SQLModel, table=True):
    route: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    request_signature: str
    response_payload: str