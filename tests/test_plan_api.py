import json
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routers.plan import router as plan_router


@pytest.fixture()
def plan_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Configure plan-related environment and return the persisted settings path."""
    plan_settings_path = tmp_path / "plan_settings.json"
    monkeypatch.setenv("PLAN_SETTINGS_FILE", str(plan_settings_path))
    return plan_settings_path


@pytest.fixture()
def plan_api_client(plan_env: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Create a FastAPI test client for the plan router with configurable env."""
    monkeypatch.setenv("DEFAULT_PLAN_TIER", "pro")
    monkeypatch.setenv("DEFAULT_PLAN_ENTITLEMENTS", "search.export")
    monkeypatch.setenv("DEFAULT_PLAN_EXPIRES_AT", "2025-12-31T00:00:00+00:00")
    # ensure override quota env is not set unless tests need it
    monkeypatch.delenv("DEFAULT_PLAN_QUOTA", raising=False)

    app = FastAPI()
    app.include_router(plan_router, prefix="/api/v1")

    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


def test_plan_context_uses_environment_defaults(plan_api_client: TestClient):
    response = plan_api_client.get("/api/v1/plan/context")
    assert response.status_code == 200

    payload = response.json()
    assert payload["planTier"] == "pro"
    # base entitlements for pro + env override should be present
    assert set(payload["entitlements"]) >= {"search.compare", "search.alerts", "evidence.inline_pdf", "search.export"}
    assert payload["expiresAt"] == "2025-12-31T00:00:00+00:00"
    assert payload["checkoutRequested"] is False

    quota = payload["quota"]
    assert quota["chatRequestsPerDay"] == 500
    assert quota["ragTopK"] == 6
    assert quota["selfCheckEnabled"] is True
    assert quota["peerExportRowLimit"] == 100


def test_plan_context_respects_request_headers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DEFAULT_PLAN_TIER", raising=False)
    monkeypatch.delenv("DEFAULT_PLAN_ENTITLEMENTS", raising=False)
    monkeypatch.delenv("DEFAULT_PLAN_EXPIRES_AT", raising=False)

    app = FastAPI()
    app.include_router(plan_router, prefix="/api/v1")
    client = TestClient(app)
    try:
        headers = {
            "x-plan-tier": "enterprise",
            "x-plan-entitlements": "alerts.force_webhook,search.export",
            "x-plan-expires-at": "2026-01-05T09:00:00+00:00",
            "x-plan-quota": "chatRequestsPerDay=42,ragTopK=2,selfCheckEnabled=false,peerExportRowLimit=75",
        }
        response = client.get("/api/v1/plan/context", headers=headers)
        assert response.status_code == 200

        payload = response.json()
        assert payload["planTier"] == "enterprise"
        assert payload["expiresAt"] == "2026-01-05T09:00:00+00:00"
        assert payload["quota"] == {
            "chatRequestsPerDay": 42,
            "ragTopK": 2,
            "selfCheckEnabled": False,
            "peerExportRowLimit": 75,
        }

        # enterprise base entitlements plus headers, sorted
        entitlements = payload["entitlements"]
        assert "search.export" in entitlements
        assert "evidence.diff" in entitlements
        assert "alerts.force_webhook" in entitlements
        assert entitlements == sorted(entitlements)
    finally:
        client.close()


def test_plan_context_patch_updates_defaults(plan_api_client: TestClient, plan_env: Path):
    payload = {
        "planTier": "enterprise",
        "entitlements": ["search.compare", "timeline.full"],
        "quota": {
            "chatRequestsPerDay": None,
            "ragTopK": 12,
            "selfCheckEnabled": True,
            "peerExportRowLimit": None,
        },
        "updatedBy": "sally@kfinance.ai",
        "changeNote": "고객 요청에 따라 Enterprise 가이드로 맞춤 적용",
        "triggerCheckout": True,
    }
    response = plan_api_client.patch("/api/v1/plan/context", json=payload, headers={"x-admin-role": "admin"})
    assert response.status_code == 200

    saved = json.loads(plan_env.read_text(encoding="utf-8"))
    assert saved["planTier"] == "enterprise"
    assert saved["entitlements"] == ["search.compare", "timeline.full"]
    assert saved["quota"]["ragTopK"] == 12
    assert saved["updatedBy"] == "sally@kfinance.ai"
    assert saved["checkoutRequested"] is True

    body = response.json()
    assert body["planTier"] == "enterprise"
    assert body["checkoutRequested"] is True
    assert body["updatedBy"] == "sally@kfinance.ai"
    assert "timeline.full" in body["entitlements"]

    reread = plan_api_client.get("/api/v1/plan/context")
    assert reread.status_code == 200
    reread_body = reread.json()
    assert reread_body["planTier"] == "enterprise"
    assert reread_body["quota"]["ragTopK"] == 12
    assert reread_body["updatedBy"] == "sally@kfinance.ai"
    assert reread_body["checkoutRequested"] is True


def test_plan_context_patch_requires_admin(plan_api_client: TestClient):
    response = plan_api_client.patch(
        "/api/v1/plan/context",
        json={
            "planTier": "pro",
            "entitlements": [],
            "quota": {
                "chatRequestsPerDay": 200,
                "ragTopK": 4,
                "selfCheckEnabled": True,
                "peerExportRowLimit": 40,
            },
        },
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "plan.unauthorized"


def test_plan_context_patch_rejects_invalid_quota(plan_api_client: TestClient):
    response = plan_api_client.patch(
        "/api/v1/plan/context",
        headers={"x-admin-role": "admin"},
        json={
            "planTier": "pro",
            "entitlements": [],
            "quota": {
                "chatRequestsPerDay": -1,
                "ragTopK": 4,
                "selfCheckEnabled": True,
                "peerExportRowLimit": 40,
            },
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "plan.invalid_payload"
