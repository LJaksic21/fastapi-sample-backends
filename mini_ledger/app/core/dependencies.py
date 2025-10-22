from fastapi import Depends
from sqlmodel import Session

from ..services import LedgerRepository, LedgerService
from .db import get_session

def get_ledger_service(session: Session = Depends(get_session)) -> LedgerService:
    repository = LedgerRepository(session)
    return LedgerService(session, repository)
