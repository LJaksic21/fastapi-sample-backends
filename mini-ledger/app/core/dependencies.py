from functools import lru_cache
from ..services import LedgerService

@lru_cache()
def get_ledger_service() -> LedgerService:
    return LedgerService()