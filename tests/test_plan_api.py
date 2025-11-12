import json
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services import plan_config_store
from web.routers.plan import router as plan_router

ADMIN_TOKEN = "test-admin-token"
ADMIN_AUTH_HEADER = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture()
def plan_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Configure plan-related environment and return the persisted settings path."""
    plan_settings_path = tmp_path / "plan_settings.json"
    monkeypatch.setenv("PLAN_SETTINGS_FILE", str(plan_settings_path))
    return plan_settings_path


@pytest.fixture()
def plan_config_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    config_path = tmp_path / "plan_config.json"
    monkeypatch.setenv("PLAN_CONFIG_FILE", str(config_path))
    plan_config_store.clear_plan_config_cache()
    try:
        yield config_path
    finally:
        plan_config_store.clear_plan_config_cache()


@pytest.fixture()
def plan_api_client(plan_env: Path, plan_config_file: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Create a FastAPI test client for the plan router with configurable env."""
    monkeypatch.setenv("DEFAULT_PLAN_TIER", "pro")
    monkeypatch.setenv("DEFAULT_PLAN_ENTITLEMENTS", "search.export")
    monkeypatch.setenv("DEFAULT_PLAN_EXPIRES_AT", "2025-12-31T00:00:00+00:00")
    # ensure override quota env is not set unless tests need it
    monkeypatch.delenv("DEFAULT_PLAN_QUOTA", raising=False)
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    monkeypatch.delenv("ADMIN_API_TOKENS", raising=False)

    app = FastAPI()
    app.include_router(plan_router, prefix="/api/v1")

    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


def test_plan_context_uses_environment_defaults(plan_api_client: TestClient):
    response = plan_api_client.get("/api/v1/plan/context")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["planTier"] == "pro"
    # base entitlements for pro + env override should be present
    assert set(payload["entitlements"]) >= {
        "search.compare",
        "search.alerts",
        "search.export",
        "evidence.inline_pdf",
        "rag.core",
    }
    assert payload["featureFlags"]["ragCore"] is True
    assert payload["expiresAt"] == "2025-12-31T00:00:00+00:00"
    assert payload["checkoutRequested"] is False

    quota = payload["quota"]
    assert quota["chatRequestsPerDay"] == 500
    assert quota["ragTopK"] == 6
    assert quota["selfCheckEnabled"] is True
    assert quota["peerExportRowLimit"] == 100
    assert payload["trial"] == {
        "tier": "pro",
        "startsAt": None,
        "endsAt": None,
        "durationDays": 7,
        "active": False,
        "used": False,
    }


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
        assert response.status_code == 200, response.text

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
        assert payload["trial"]["tier"] == "pro"
        assert payload["trial"]["active"] is False
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
    response = plan_api_client.patch("/api/v1/plan/context", json=payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200, response.text

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
    assert reread.status_code == 200, reread.text
    reread_body = reread.json()
    assert reread_body["planTier"] == "enterprise"
    assert reread_body["quota"]["ragTopK"] == 12
    assert reread_body["updatedBy"] == "sally@kfinance.ai"
    assert reread_body["checkoutRequested"] is True
    assert reread_body["trial"]["tier"] == "pro"


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
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "plan.unauthorized"


def test_plan_context_patch_rejects_invalid_quota(plan_api_client: TestClient):
    response = plan_api_client.patch(
        "/api/v1/plan/context",
        headers=ADMIN_AUTH_HEADER,
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
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "plan.invalid_payload"


def test_plan_trial_endpoint_starts_trial(plan_api_client: TestClient, plan_env: Path):
    response = plan_api_client.post(
        "/api/v1/plan/trial",
        json={
            "actor": "sejin@kfinance.ai",
            "durationDays": 5,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["trial"]["active"] is True
    assert payload["trial"]["used"] is True
    assert payload["trial"]["durationDays"] == 5
    assert payload["trial"]["tier"] == "pro"

    saved = json.loads(plan_env.read_text(encoding="utf-8"))
    assert saved["trial"]["used"] is True
    assert saved["trial"]["durationDays"] == 5
    assert saved["trial"]["startedAt"] is not None
    assert saved["trial"]["endsAt"] is not None

    # second request should be rejected because the trial is already used
    second = plan_api_client.post("/api/v1/plan/trial", json={"actor": "someone@kfinance.ai"})
    assert second.status_code == 400
    second_detail = second.json()["detail"]
    assert second_detail["code"] == "plan.trial_unavailable"


def test_plan_patch_preserves_trial_state(plan_api_client: TestClient, plan_env: Path):
    # start the trial first
    trial_resp = plan_api_client.post("/api/v1/plan/trial", json={"actor": "trialer@kfinance.ai"})
    assert trial_resp.status_code == 200, trial_resp.text

    payload = {
        "planTier": "pro",
        "entitlements": ["search.compare"],
        "quota": {
            "chatRequestsPerDay": 300,
            "ragTopK": 4,
            "selfCheckEnabled": True,
            "peerExportRowLimit": 10,
        },
        "updatedBy": "admin@kfinance.ai",
    }
    response = plan_api_client.patch("/api/v1/plan/context", json=payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200, response.text

    saved = json.loads(plan_env.read_text(encoding="utf-8"))
    assert "trial" in saved
    assert saved["trial"]["used"] is True
    assert saved["trial"]["startedAt"] is not None
    assert saved["trial"]["endsAt"] is not None


def test_plan_presets_update(plan_api_client: TestClient, plan_config_file: Path):
    payload = {
        "tiers": [
            {
                "tier": "free",
                "entitlements": ["search.alerts"],
                "quota": {
                    "chatRequestsPerDay": 10,
                    "ragTopK": 2,
                    "selfCheckEnabled": False,
                    "peerExportRowLimit": 0,
                },
            },
            {
                "tier": "pro",
                "entitlements": ["search.compare", "search.alerts", "search.export"],
                "quota": {
                    "chatRequestsPerDay": 600,
                    "ragTopK": 8,
                    "selfCheckEnabled": True,
                    "peerExportRowLimit": 200,
                },
            },
        ],
        "updatedBy": "ops@kfinance.ai",
        "note": "alert builder free tier 허용",
    }
    response = plan_api_client.put("/api/v1/plan/presets", json=payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200, response.text
    body = response.json()
    tiers = {entry["tier"]: entry for entry in body["presets"]}
    assert tiers["free"]["entitlements"] == ["search.alerts"]
    assert tiers["pro"]["quota"]["chatRequestsPerDay"] == 600
    assert set(tiers["pro"]["entitlements"]) == {"search.compare", "search.alerts", "search.export"}

    reread = plan_api_client.get("/api/v1/plan/presets")
    assert reread.status_code == 200
    reread_body = reread.json()
    pro_entry = next(item for item in reread_body["presets"] if item["tier"] == "pro")
    assert set(pro_entry["entitlements"]) == {"search.compare", "search.alerts", "search.export"}
    assert pro_entry["quota"]["ragTopK"] == 8

    saved = json.loads(plan_config_file.read_text(encoding="utf-8"))
    assert saved["tiers"]["pro"]["quota"]["peerExportRowLimit"] == 200
    assert saved["updated_by"] == "ops@kfinance.ai"
