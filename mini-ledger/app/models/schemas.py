from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

class AccountCreate(BaseModel):
    owner_name: str = Field(..., min_length=1, description="Name of the account holder")

class AccountResponse(BaseModel):
    id: UUID
    owner_name: str
    created_at: datetime
    balance: int = Field(..., ge=0, description="Balance in minor units (e.g. cents)")

class LedgerEntryResponse(BaseModel):
    id: UUID
    ts: datetime
    account_id: UUID
    amount: int
    type: Literal["DEBIT", "CREDIT"]
    ref: Optional[str] = Field(default=None, description="Human-readable memo or reference")

class MoneyMovementRequest(BaseModel):
    amount: int = Field(..., ge=1, description="Amount in minor units (must be >= 1)")
    memo: Optional[str] = Field(default=None, description="Narrative to display on the statement")

class TransferRequest(BaseModel):
    source_account_id: UUID
    dest_account_id: UUID
    amount: int = Field(..., ge=1)
    memo: Optional[str] = None

class StatementResponse(BaseModel):
    items: list[LedgerEntryResponse]
    next_cursor: Optional[str] = None
