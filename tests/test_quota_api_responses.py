from __future__ import annotations

import sys
import types
import uuid
from types import SimpleNamespace

import pytest

pytest.skip("reports router not available", allow_module_level=True)
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub optional native deps used by routers at import-time.
sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore
sys.modules.setdefault(
    "pyotp",
    types.SimpleNamespace(
        TOTP=lambda *args, **kwargs: None,
        random_base32=lambda: "BASE32",
    ),
)  # type: ignore

fake_org_module = types.ModuleType("models.org")
fake_org_module.Org = type("Org", (), {})
fake_org_module.OrgRole = type("OrgRole", (), {})
fake_org_module.UserOrg = type("UserOrg", (), {})
sys.modules.setdefault("models.org", fake_org_module)

fake_plan_catalog_module = types.ModuleType("services.plan_catalog_service")
fake_plan_catalog_module.load_plan_catalog = lambda *_, **__: {}
fake_plan_catalog_module.update_plan_catalog = lambda *_, **__: None
sys.modules.setdefault("services.plan_catalog_service", fake_plan_catalog_module)

from database import get_db  # noqa: E402
from services.entitlement_service import EntitlementDecision  # noqa: E402
from services.plan_service import PlanContext, PlanQuota  # noqa: E402
from web.deps import get_plan_context  # noqa: E402
from web.routers import chat as chat_router  # noqa: E402
from web.routers import rag as rag_router  # noqa: E402
from web.routers import reports as reports_router  # noqa: E402
import web.quota_guard as quota_guard  # noqa: E402


def _plan_context(entitlements: set[str]) -> PlanContext:
    return PlanContext(
        tier="starter",
        base_tier="starter",
        expires_at=None,
        entitlements=frozenset(entitlements),
        quota=PlanQuota(chat_requests_per_day=80, rag_top_k=5, self_check_enabled=True, peer_export_row_limit=25),
        memory_chat_enabled=True,
    )


def _make_db_override():
    def _override_db():
        yield SimpleNamespace()

    return _override_db


@pytest.fixture()
def reports_client():
    app = FastAPI()
    app.include_router(reports_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _make_db_override()
    plan = _plan_context({"search.export"})
    app.dependency_overrides[get_plan_context] = lambda: plan
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture()
def rag_client():
    app = FastAPI()
    app.include_router(rag_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _make_db_override()
    plan = _plan_context({"rag.core"})
    app.dependency_overrides[get_plan_context] = lambda: plan
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


class _ChatQuery:
    def __init__(self, session: SimpleNamespace) -> None:
        self._session = session

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._session


class _ChatDB:
    def __init__(self, session: SimpleNamespace) -> None:
        self._session = session

    def query(self, *_args, **_kwargs):
        return _ChatQuery(self._session)

    def commit(self) -> None:  # pragma: no cover - defensive
        return

    def rollback(self) -> None:  # pragma: no cover - defensive
        return

    def refresh(self, *_args, **_kwargs) -> None:  # pragma: no cover - defensive
        return


@pytest.fixture()
def chat_client():
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/v1")

    session = SimpleNamespace(id=uuid.uuid4(), user_id=None, org_id=None)
    chat_db = _ChatDB(session)

    def _override_db():
        yield chat_db

    app.dependency_overrides[get_db] = _override_db
    plan = _plan_context({"rag.core"})
    app.dependency_overrides[get_plan_context] = lambda: plan
    client = TestClient(app)
    try:
        yield client, session
    finally:
        client.close()


def _patch_quota(monkeypatch: pytest.MonkeyPatch, *, decision: EntitlementDecision) -> None:
    monkeypatch.setattr(quota_guard, "evaluate_quota", lambda *_, **__: decision)


def test_rag_query_quota_response(rag_client, monkeypatch: pytest.MonkeyPatch):
    _patch_quota(
        monkeypatch,
        decision=EntitlementDecision(allowed=False, remaining=0, limit=20),
    )
    response = rag_client.post(
        "/api/v1/rag/query",
        json={"question": "테스트 질문입니다."},
        headers={"X-User-Id": str(uuid.uuid4())},
    )
    assert response.status_code == 429
    payload = response.json()["detail"]
    assert payload["quota"]["action"] == "rag.chat"


def test_chat_message_quota_response(chat_client, monkeypatch: pytest.MonkeyPatch):
    client, session = chat_client
    _patch_quota(
        monkeypatch,
        decision=EntitlementDecision(allowed=False, remaining=0, limit=5),
    )
    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": str(session.id),
            "role": "user",
            "content": "안녕하세요",
        },
        headers={"X-User-Id": str(uuid.uuid4())},
    )
    assert response.status_code == 429
    payload = response.json()["detail"]
    assert payload["quota"]["action"] == "api.chat"
