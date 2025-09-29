# fastapi-sample-backends
Repo to practice setting up basic FastAPI backends.

## Requirements Doc #1 — Mini Ledger: Accounts, Transfers, and Statement

### Theme & Difficulty
- Core fintech ledger logic, data integrity, idempotency
- Medium difficulty (60–75 min)

### Goal
Expose a simple double-entry ledger API: create accounts, deposit/withdraw, transfer between accounts, and fetch a statement. Prevent negative balances. Support idempotent POSTs.

### Environment & Allowed Tools
- Python 3.11+
- fastapi, uvicorn, pydantic
- Optional: sqlmodel/sqlite3; in-memory data storage is acceptable

### Testing
- pytest + httpx test client (or starlette.testclient)

### Data Model (Minimal)
- `Account`: `{id: str(UUID), owner_name: str, created_at: datetime, balance: int}` (balance in minor units: cents)
- `LedgerEntry`: `{id: UUID, ts: datetime, account_id: UUID, amount: int, type: "DEBIT"|"CREDIT", ref: str}`
- `Transfer`: logical pair of entries (CREDIT destination, DEBIT source) under one `transfer_id`
- Using integer cents avoids float errors.

### Endpoints
1. `POST /accounts` → Body `{owner_name: str}` → `201` response `{"id": "...", "owner_name": "...", "balance": 0, "created_at": ...}`
2. `POST /accounts/{id}/deposit` → Headers `Idempotency-Key: <uuid>` (required), Body `{amount: int >=1, memo?: str}` → `200` returns updated account (repeat with same idempotency key is a no-op and returns the same response)
3. `POST /accounts/{id}/withdraw` → Headers `Idempotency-Key` required, Body `{amount: int >=1, memo?: str}` → `409` if insufficient funds
4. `POST /transfers` → Headers `Idempotency-Key` required, Body `{source_account_id: UUID, dest_account_id: UUID, amount: int >=1, memo?: str}` → Prevent self-transfer; `409` if insufficient funds; operation must be atomic
5. `GET /accounts/{id}` → Account snapshot
6. `GET /accounts/{id}/statement?limit=50&cursor=<token>` → Returns recent ledger entries (newest first) with cursor-based pagination → Response `{items: [...], next_cursor: "abc" | null}`

### Business Rules
- No negative balances; withdrawals and transfers enforce this constraint.
- Double-entry invariant: each transfer produces one DEBIT and one CREDIT with equal magnitude.
- Idempotency: the same `Idempotency-Key` on the same route & body returns identical results; maintain a small key→result map.

### Error Handling
- `400` invalid input
- `404` not found
- `409` conflict (insufficient funds or duplicate transfer with different body)
- `422` validation

### Required Test Scenarios (Write 5–7)
- Create accounts; deposit; withdraw happy path.
- Insufficient funds returns `409`.
- Transfer creates two entries and conserves total.
- Idempotent deposit: second call returns same payload with no duplicate effect.
- Statement returns reverse-chronological entries; pagination works.

### Evaluation Rubric (Suggested)
- Correctness 40% (rules & invariants)
- API design & validation 25%
- Code structure & clarity 20%
- Tests 10%
- Extras 5% (e.g., simple JWT auth, README, OpenAPI examples)

### Stretch Goals
- JWT bearer on mutating routes
- BackgroundTasks to asynchronously post a “receipt”
- Swap in SQLite
