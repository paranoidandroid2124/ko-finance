from types import SimpleNamespace

import pytest

from services.payments import toss_webhook_replay as replay


def _make_record(payload, **kwargs):
    return SimpleNamespace(
        payload=payload,
        context=kwargs.get("context", {}),
        status=kwargs.get("status"),
        retry_count=kwargs.get("retry_count"),
    )


@pytest.fixture(autouse=True)
def reset_monkeypatch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(replay, "append_webhook_audit_entry", lambda **_kwargs: None)
    monkeypatch.setattr(replay, "record_webhook_event", lambda **_kwargs: None)


def test_replay_applies_upgrade(monkeypatch: pytest.MonkeyPatch):
    payload = {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "data": {"status": "DONE", "orderId": "kfinance-enterprise-001"},
    }
    monkeypatch.setattr(replay, "_load_webhook_record", lambda transmission_id: _make_record(payload))
    applied = {}

    def _apply_checkout_upgrade(**kwargs):
        applied.update(kwargs)

    monkeypatch.setattr(replay, "apply_checkout_upgrade", _apply_checkout_upgrade)
    monkeypatch.setattr(replay, "clear_checkout_requested", lambda **_kwargs: None)

    result = replay.replay_toss_webhook_event("trans-1")

    assert result["status"] == "DONE"
    assert result["tier"] == "enterprise"
    assert applied["target_tier"] == "enterprise"
    assert applied["updated_by"] == "toss-webhook-replay"


def test_replay_clears_checkout(monkeypatch: pytest.MonkeyPatch):
    payload = {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "data": {"status": "CANCELED", "orderId": "kfinance-pro-001"},
    }
    monkeypatch.setattr(replay, "_load_webhook_record", lambda transmission_id: _make_record(payload))
    monkeypatch.setattr(replay, "apply_checkout_upgrade", lambda **_kwargs: None)
    cleared = {}

    def _clear_checkout_requested(**kwargs):
        cleared.update(kwargs)

    monkeypatch.setattr(replay, "clear_checkout_requested", _clear_checkout_requested)

    result = replay.replay_toss_webhook_event("trans-2")

    assert result["status"] == "CANCELED"
    assert cleared["updated_by"] == "toss-webhook-replay"


def test_replay_missing_event(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(replay, "_load_webhook_record", lambda transmission_id: None)
    with pytest.raises(ValueError):
        replay.replay_toss_webhook_event("missing")
