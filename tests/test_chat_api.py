import sys
import types
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore
import web.routers.chat as chat


class FakeDB:
    def __init__(self, session):
        self.session = session
        self.committed = False
        self.rolled_back = False
        self.refreshed = False

    def query(self, model):  # pragma: no cover - interface stub
        return self

    def filter(self, *args, **kwargs):  # pragma: no cover - interface stub
        return self

    def first(self):
        return self.session

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, _):
        self.refreshed = True


@pytest.fixture()
def chat_test_client(monkeypatch):
    app = FastAPI()
    app.include_router(chat.router, prefix="/api/v1")

    session = SimpleNamespace(id=uuid.uuid4(), user_id=None, org_id=None, archived_at=None)
    fake_db = FakeDB(session)

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    captured = {}

    def fake_create_chat_message(
        db,
        *,
        session_id,
        role,
        content,
        turn_id,
        idempotency_key,
        reply_to_message_id=None,
        retry_of_message_id=None,
        meta=None,
        state="pending",
    ):
        captured["turn_id"] = turn_id
        captured["state"] = state
        captured["session_id"] = session_id
        return SimpleNamespace(
            id=uuid.uuid4(),
            session_id=session_id,
            seq=1,
            turn_id=turn_id,
            retry_of_message_id=retry_of_message_id,
            reply_to_message_id=reply_to_message_id,
            role=role,
            state=state,
            error_code=None,
            error_message=None,
            content=content,
            meta=meta or {},
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(chat.chat_service, "create_chat_message", fake_create_chat_message)

    client = TestClient(app)
    try:
        yield client, fake_db, captured
    finally:
        client.close()


def test_create_message_accepts_string_turn_id(chat_test_client):
    client, fake_db, captured = chat_test_client
    turn_identifier = "_3SdPFePo1xS-ipRSKXWx"

    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": str(fake_db.session.id),
            "role": "user",
            "content": "안녕하세요",
            "turn_id": turn_identifier,
            "state": "pending",
            "meta": {"turnId": turn_identifier},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert captured["turn_id"].version == 5
    assert payload["turn_id"] == str(captured["turn_id"])
    assert payload["meta"]["turnId"] == turn_identifier
    assert fake_db.committed is True
    assert fake_db.refreshed is True


def test_create_message_generates_uuid_when_missing(chat_test_client):
    client, fake_db, captured = chat_test_client

    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": str(fake_db.session.id),
            "role": "assistant",
            "content": "초기화 중입니다",
            "state": "pending",
            "meta": {"turnId": None},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert captured["turn_id"].version == 4
    assert payload["turn_id"] == str(captured["turn_id"])
    assert fake_db.committed is True
    assert fake_db.refreshed is True
