import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from ..core.config import get_settings
from ..core.db import create_engine_for_url, get_session, init_db, set_engine
from ..main import app

@pytest.fixture
def client(tmp_path) -> TestClient:
    test_db = tmp_path / "test.db"
    engine = create_engine_for_url(f"sqlite:///{test_db}")
    original_engine = create_engine_for_url(get_settings().database_url)
    set_engine(engine)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    def _get_session_override():
        with Session(engine) as session:
            yield session
    
    app.dependency_overrides[get_session] = _get_session_override
    init_db()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    set_engine(original_engine)
    init_db()


def test_create_account_deposit_withdraw(client: TestClient) -> None:
    response = client.post("/accounts", json={"owner_name": "Alice"})
    assert response.status_code == 201
    account = response.json()
    account_id = account["id"]

    deposit = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 1000},
        headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert deposit.status_code == 200
    assert deposit.json()["balance"] == 1000

    withdraw = client.post(
        f"/accounts/{account_id}/withdraw",
        json={"amount": 400},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["balance"] == 600

def test_withdraw_insufficient_funds(client: TestClient) -> None:
    account_id = client.post("/accounts", json={"owner_name": "Bob"}).json()["id"]

    response = client.post(
        f"/accounts/{account_id}/withdraw",
        json={"amount": 1},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 409

def test_transfer_creates_two_entries(client: TestClient) -> None:
    source_id = client.post("/accounts", json={"owner_name": "Carol"}).json()["id"]
    dest_id = client.post("/accounts", json={"owner_name": "Dave"}).json()["id"]

    client.post(
        f"/accounts/{source_id}/deposit",
        json={"amount": 2000},
        headers={"Idempotency-Key": str(uuid.uuid4())}
    )

    transfer = client.post(
        "/transfers",
        json={
            "source_account_id": source_id,
            "dest_account_id": dest_id,
            "amount": 750,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert transfer.status_code == 200
    payload = transfer.json()
    assert payload["source"]["balance"] == 1250
    assert payload["dest"]["balance"] == 750

def test_deposit_idempotency(client: TestClient) -> None:
    account_id = client.post("/accounts", json={"owner_name": "Eve"}).json()["id"]
    key = str(uuid.uuid4())
    first = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 500},
        headers={"Idempotency-Key": key},
    )
    second = client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 500},
        headers={"Idempotency-Key": key},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    snapshot = client.get(f"/accounts/{account_id}")
    assert snapshot.json()["balance"] == 500

def test_statement_pagination(client: TestClient) -> None:
    account_id = client.post("/accounts", json={"owner_name": "Frank"}).json()["id"]

    for amount in (100, 200, 300):
        client.post(
            f"/accounts/{account_id}/deposit",
            json={"amount": amount},
            headers={"Idempotency-Key": str(uuid.uuid4())}
        )

    first_page = client.get(f"/accounts/{account_id}/statement", params={"limit": 2})
    assert first_page.status_code == 200
    items = first_page.json()["items"]
    assert len(items) == 2
    # Ensure newest first: amounts should be 300, then 200
    assert [entry["amount"] for entry in items] == [300, 200]

    cursor = first_page.json()["next_cursor"]
    second_page = client.get(
        f"/accounts/{account_id}/statement", params={"cursor": cursor}
    )
    remain = second_page.json()["items"]
    assert len(remain) == 1
    assert remain[0]["amount"] == 100
    assert second_page.json()["next_cursor"] is None


def test_transfer_rejects_self_transfer(client: TestClient) -> None:
    account_id = client.post("/accounts", json={"owner_name": "George"}).json()["id"]

    client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 500},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    response = client.post(
        "/transfers",
        json={
            "source_account_id": account_id,
            "dest_account_id": account_id,
            "amount": 100,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot transfer to the same account"


def test_statement_invalid_cursor_returns_400(client: TestClient) -> None:
    account_id = client.post("/accounts", json={"owner_name": "Helen"}).json()["id"]

    client.post(
        f"/accounts/{account_id}/deposit",
        json={"amount": 100},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    response = client.get(
        f"/accounts/{account_id}/statement",
        params={"cursor": "not-a-valid-timestamp"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid cursor"
