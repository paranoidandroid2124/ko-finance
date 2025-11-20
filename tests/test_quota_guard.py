import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.entitlement_service import EntitlementDecision
from web import quota_guard


def _plan(tier: str = "starter"):
    return SimpleNamespace(tier=tier)


def test_enforce_quota_allows_when_under_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = EntitlementDecision(allowed=True, remaining=5, limit=10)
    monkeypatch.setattr(quota_guard, "evaluate_quota", lambda *_, **__: decision)

    quota_guard.enforce_quota("rag.chat", plan=_plan(), user_id=uuid.uuid4(), org_id=None)


def test_enforce_quota_raises_when_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = EntitlementDecision(allowed=False, remaining=0, limit=10)
    monkeypatch.setattr(quota_guard, "evaluate_quota", lambda *_, **__: decision)

    with pytest.raises(HTTPException) as exc:
        quota_guard.enforce_quota("watchlist.preview", plan=_plan("starter"), user_id=uuid.uuid4(), org_id=None)

    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "plan.quota_exceeded"
    assert exc.value.detail["planTier"] == "starter"


def test_enforce_quota_raises_for_unavailable_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = EntitlementDecision(allowed=False, remaining=0, limit=0)
    monkeypatch.setattr(quota_guard, "evaluate_quota", lambda *_, **__: decision)

    with pytest.raises(HTTPException) as exc:
        quota_guard.enforce_quota("api.chat", plan=_plan("free"), user_id=uuid.uuid4(), org_id=None)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "plan.quota_unavailable"
