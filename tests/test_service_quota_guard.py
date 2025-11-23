from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from services import quota_guard
from services.entitlement_service import EntitlementDecision


def test_consume_quota_skips_when_subject_missing(monkeypatch):
    tracker = {"called": False}

    def _not_expected(**_kwargs):
        tracker["called"] = True
        return EntitlementDecision(allowed=True, remaining=None, limit=None)

    monkeypatch.setattr(quota_guard, "entitlement_service", SimpleNamespace(consume=_not_expected))
    assert quota_guard.consume_quota("rag.chat", user_id=None, org_id=None) is True
    assert tracker["called"] is False


def test_consume_quota_normalizes_subject(monkeypatch):
    captured = {}
    decision = EntitlementDecision(allowed=True, remaining=4, limit=10)

    def _fake_consume(**kwargs):
        captured.update(kwargs)
        return decision

    monkeypatch.setattr(quota_guard, "entitlement_service", SimpleNamespace(consume=_fake_consume))
    user_id = uuid4()
    assert quota_guard.consume_quota("rag.chat", user_id=user_id, org_id=None) is True
    assert captured["user_id"] == user_id
    assert captured["org_id"] == user_id


def test_consume_quota_returns_false_when_blocked(monkeypatch):
    decision = EntitlementDecision(allowed=False, remaining=0, limit=5)
    monkeypatch.setattr(quota_guard, "entitlement_service", SimpleNamespace(consume=lambda **_: decision))
    assert quota_guard.consume_quota("rag.chat", user_id=uuid4(), org_id=None) is False
