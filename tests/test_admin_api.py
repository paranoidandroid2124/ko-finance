import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services import plan_service
from web.routers.admin import router as admin_router

ADMIN_TOKEN = "test-admin-token"
ADMIN_AUTH_HEADER = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture()
def admin_plan_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    plan_settings_path = tmp_path / "plan_settings.json"
    monkeypatch.setattr(plan_service, "_DEFAULT_PLAN_SETTINGS_PATH", plan_settings_path)
    plan_service._PLAN_SETTINGS_CACHE = None
    plan_service._PLAN_SETTINGS_CACHE_PATH = None
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("ADMIN_API_ACTOR", "qa-admin@kfinance.ai")
    monkeypatch.delenv("ADMIN_API_TOKENS", raising=False)

    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1")

    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        plan_service._PLAN_SETTINGS_CACHE = None
        plan_service._PLAN_SETTINGS_CACHE_PATH = None


def test_admin_session_endpoint(admin_plan_env: TestClient) -> None:
    response = admin_plan_env.get("/api/v1/admin/session", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    payload = response.json()
    assert payload["actor"] == "qa-admin@kfinance.ai"
    assert payload["issuedAt"]
    assert payload["tokenHint"]


def test_list_toss_webhook_events(monkeypatch: pytest.MonkeyPatch, admin_plan_env: TestClient) -> None:
    sample = [
        {
            "loggedAt": datetime.now(timezone.utc).isoformat(),
            "result": "processed",
            "message": None,
            "context": {"order_id": "kfinance-pro-001"},
            "payload": {"status": "DONE"},
        }
    ]
    monkeypatch.setattr("web.routers.admin.read_recent_webhook_entries", lambda limit=100: sample)

    response = admin_plan_env.get("/api/v1/admin/webhooks/toss/events?limit=50", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["result"] == "processed"
    assert payload["items"][0]["context"]["order_id"] == "kfinance-pro-001"


def test_replay_toss_webhook(monkeypatch: pytest.MonkeyPatch, admin_plan_env: TestClient) -> None:
    monkeypatch.setattr(
        "web.routers.admin.replay_toss_webhook_event",
        lambda transmission_id: {"status": "DONE", "orderId": "order-1", "tier": "enterprise"},
    )

    response = admin_plan_env.post(
        "/api/v1/admin/webhooks/toss/replay",
        json={"transmissionId": "trans-1"},
        headers=ADMIN_AUTH_HEADER,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "DONE"
    assert payload["orderId"] == "order-1"
    assert payload["tier"] == "enterprise"


def test_plan_quick_adjust_updates_settings(admin_plan_env: TestClient, tmp_path: Path) -> None:
    payload = {
        "planTier": "enterprise",
        "entitlements": ["search.compare", "search.export"],
        "quota": {
            "chatRequestsPerDay": None,
            "ragTopK": 10,
            "selfCheckEnabled": True,
            "peerExportRowLimit": None,
        },
        "expiresAt": "2027-01-01T00:00:00+00:00",
        "actor": "qa-admin@kfinance.ai",
        "changeNote": "Admin quick adjust test",
        "triggerCheckout": False,
        "forceCheckoutRequested": False,
    }

    response = admin_plan_env.post("/api/v1/admin/plan/quick-adjust", json=payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["planTier"] == "enterprise"
    assert body["updatedBy"] == "qa-admin@kfinance.ai"
    assert body["checkoutRequested"] is False
    assert body["featureFlags"]["searchCompare"] is True
    assert body["featureFlags"]["searchExport"] is True
    assert body["quota"]["ragTopK"] == 10

    saved = json.loads(plan_service._DEFAULT_PLAN_SETTINGS_PATH.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
    assert saved["planTier"] == "enterprise"
    assert saved["checkoutRequested"] is False
    assert saved["entitlements"] == ["search.compare", "search.export"]
