import uuid
from datetime import datetime, timezone
from typing import Iterator, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import get_db
from models.filing import Filing
from web.routers import public


@pytest.fixture()
def public_test_client(db_session: Session) -> Iterator[Tuple[TestClient, Session]]:
    app = FastAPI()
    app.include_router(public.router, prefix="/api/v1")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, db_session
    finally:
        client.close()


def _insert_filing(db_session: Session, *, corp_name: str = "테스트 기업") -> Filing:
    filing = Filing(
        id=uuid.uuid4(),
        corp_name=corp_name,
        report_name="사업보고서",
        filed_at=datetime.now(timezone.utc),
        market="KOSPI",
        category="사업보고",
        title="테스트 공시",
    )
    db_session.add(filing)
    db_session.flush()
    return filing


def test_public_filings_returns_recent_items(public_test_client: Tuple[TestClient, Session]) -> None:
    client, db_session = public_test_client
    filing = _insert_filing(db_session)

    response = client.get("/api/v1/public/filings?limit=3")
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["filings"]]
    assert str(filing.id) in ids


def test_public_chat_preview_returns_answer(public_test_client: Tuple[TestClient, Session]) -> None:
    client, db_session = public_test_client
    filing = _insert_filing(db_session, corp_name="한빛전자")

    response = client.post("/api/v1/public/chat", json={"question": "최근 공시 동향 알려줘"})
    assert response.status_code == 200
    payload = response.json()
    assert "최근 공시" in payload["answer"]
    assert "한빛전자" in payload["answer"]
    assert payload["sources"]
    assert payload["sources"][0]["id"] == str(filing.id)
    assert payload["disclaimer"]
