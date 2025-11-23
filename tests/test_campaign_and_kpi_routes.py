from __future__ import annotations

import importlib.util
import pytest

pytest.skip("analytics router removed", allow_module_level=True)
import json
import sys
import types
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

fake_org_module = types.ModuleType("models.org")
fake_org_module.Org = type("Org", (), {})
fake_org_module.OrgRole = type("OrgRole", (), {})
fake_org_module.UserOrg = type("UserOrg", (), {})
sys.modules.setdefault("models.org", fake_org_module)

if "web" not in sys.modules:
    web_pkg = types.ModuleType("web")
    web_pkg.__path__ = [str(Path("web").resolve())]
    sys.modules["web"] = web_pkg

routers_pkg = types.ModuleType("web.routers")
routers_pkg.__path__ = [str(Path("web/routers").resolve())]
sys.modules["web.routers"] = routers_pkg

from services import campaign_settings_service
from web.deps_rbac import RbacState


def _load_router_module(dotted_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(dotted_name, Path(relative_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    sys.modules[dotted_name] = module
    return module


analytics_module = _load_router_module("web.routers.analytics", "web/routers/analytics.py")
campaign_module = _load_router_module("web.routers.campaign", "web/routers/campaign.py")


def _campaign_client() -> TestClient:
    app = FastAPI()
    app.include_router(campaign_module.router, prefix="/api/v1")
    return TestClient(app)


def _analytics_client(fake_state: RbacState) -> TestClient:
    app = FastAPI()
    app.include_router(analytics_module.router, prefix="/api/v1")
    app.dependency_overrides[analytics_module.get_rbac_state] = lambda: fake_state
    return TestClient(app)


def test_campaign_settings_endpoint_uses_config_file(tmp_path, monkeypatch):
    payload = {
        "starter_promo": {
            "enabled": True,
            "banner": {
                "headline": "신규 Starter 프로모션",
                "body": "맞춤 워치리스트와 알림을 즉시 시작하세요.",
                "ctaLabel": "업그레이드",
                "dismissLabel": "다음에 보기",
            },
            "emails": [
                {
                    "id": "invite",
                    "subject": "Starter 체험을 시작하세요",
                    "preview": "워치리스트 자동화 안내",
                    "bodyTemplate": "emails/campaigns/starter.html",
                }
            ],
            "kpi": {"events": ["campaign.test"], "sinks": ["telemetry"]},
        }
    }
    path = tmp_path / "campaign_settings.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setenv("CAMPAIGN_SETTINGS_FILE", str(path))
    campaign_settings_service.clear_campaign_settings_cache()

    client = _campaign_client()
    response = client.get("/api/v1/campaign/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["starter_promo"]["enabled"] is True
    assert data["starter_promo"]["banner"]["headline"] == "신규 Starter 프로모션"
    assert data["starter_promo"]["emails"][0]["id"] == "invite"
    assert data["starter_promo"]["kpi"]["events"] == ["campaign.test"]


def test_analytics_event_records_kpi(monkeypatch):
    captured = {}

    def _fake_record_kpi_event(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(analytics_module, "record_kpi_event", _fake_record_kpi_event)
    monkeypatch.setattr(analytics_module, "is_allowed_event", lambda name: name == "campaign.starter.banner_click")

    fake_state = RbacState(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        membership=None,
        issue=None,
        enforce_default=False,
    )
    client = _analytics_client(fake_state)

    payload = {"name": "campaign.starter.banner_click", "payload": {"foo": "bar"}}
    response = client.post("/api/v1/analytics/event", json=payload)
    assert response.status_code == 202
    assert captured["name"] == payload["name"]
    assert captured["payload"] == payload["payload"]
    assert captured["source"] == "campaign"


def test_analytics_event_requires_user(monkeypatch):
    client = _analytics_client(
        RbacState(
            user_id=None,
            org_id=None,
            membership=None,
            issue=None,
            enforce_default=False,
        )
    )
    response = client.post("/api/v1/analytics/event", json={"name": "campaign.starter.banner_click", "payload": {}})
    assert response.status_code == 401


def test_analytics_event_validates_allowlist(monkeypatch):
    client = _analytics_client(
        RbacState(
            user_id=uuid.uuid4(),
            org_id=None,
            membership=None,
            issue=None,
            enforce_default=False,
        )
    )
    response = client.post("/api/v1/analytics/event", json={"name": "unknown.event", "payload": {}})
    assert response.status_code == 400
