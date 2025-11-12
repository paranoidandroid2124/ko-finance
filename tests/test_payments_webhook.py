from __future__ import annotations

import sys
import types
import uuid

import pytest

fake_plan_catalog_module = types.ModuleType("services.plan_catalog_service")
fake_plan_catalog_module.load_plan_catalog = lambda *_, **__: {}
fake_plan_catalog_module.update_plan_catalog = lambda *_, **__: None
sys.modules.setdefault("services.plan_catalog_service", fake_plan_catalog_module)

from web.routers import payments


def test_sync_entitlement_subscription_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def _fake_sync_subscription(org_id, plan_slug, status, current_period_end, metadata):
        captured["org_id"] = org_id
        captured["plan_slug"] = plan_slug
        captured["status"] = status
        captured["metadata"] = metadata

    monkeypatch.setattr(payments.entitlement_service, "sync_subscription_from_billing", _fake_sync_subscription)

    fallback_org = uuid.uuid4()
    event = {"data": {"status": "DONE", "metadata": {}}}
    result = payments._sync_entitlement_subscription(
        plan_slug="starter",
        status="DONE",
        order_id="kfinance-starter-123",
        event=event,
        log_context={},
        fallback_org_id=fallback_org,
        fallback_metadata={"orgId": str(fallback_org)},
    )

    assert result == fallback_org
    assert captured["org_id"] == fallback_org
    assert captured["plan_slug"] == "starter"
    assert captured["metadata"]["fallback"]["orgId"] == str(fallback_org)
