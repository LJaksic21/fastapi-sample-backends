class AccountNotFoundError[Exception]:
    """Raised when an account id is missing from the store."""

class InsufficientFundsError[Exception]:
    """Raised when a withdrawal/transfer would drop balance below zero."""

class DuplicateIdempotencyKeyError[Exception]:
    """Raised when the same idempotency key is reused with different input."""