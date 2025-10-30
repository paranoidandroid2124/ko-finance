import json
from pathlib import Path

import pytest

from services.payments import toss_webhook_store as store


@pytest.fixture(autouse=True)
def _isolate_webhook_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the webhook store to a temporary path per test and reset caches."""
    path = tmp_path / "toss_webhook_events.json"
    monkeypatch.setattr(store, "_WEBHOOK_STATE_PATH", path)
    store._EVENT_CACHE = None  # type: ignore[attr-defined]
    store._EVENT_CACHE_PATH = None  # type: ignore[attr-defined]
    yield path
    store._EVENT_CACHE = None  # type: ignore[attr-defined]
    store._EVENT_CACHE_PATH = None  # type: ignore[attr-defined]


def _load_raw_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("events", [])


def test_record_and_detect_processed_webhook(_isolate_webhook_store: Path) -> None:
    assert store.has_processed_webhook("order-1") is False

    store.record_webhook_event(
        key="order-1",
        transmission_id="trans-1",
        order_id="order-1",
        status="DONE",
        event_type="PAYMENT_STATUS_CHANGED",
    )

    assert store.has_processed_webhook("order-1") is True
    events = _load_raw_events(_isolate_webhook_store)
    assert len(events) == 1
    assert events[0]["key"] == "order-1"
    assert events[0]["transmission_id"] == "trans-1"


def test_record_overwrites_existing_entry(_isolate_webhook_store: Path) -> None:
    store.record_webhook_event(
        key="order-1",
        transmission_id="initial",
        order_id="order-1",
        status="DONE",
        event_type="PAYMENT_STATUS_CHANGED",
    )
    first_events = _load_raw_events(_isolate_webhook_store)
    first_processed_at = first_events[0]["processed_at"]

    store.record_webhook_event(
        key="order-1",
        transmission_id="update",
        order_id="order-1",
        status="CANCELED",
        event_type="PAYMENT_STATUS_CHANGED",
    )

    events = _load_raw_events(_isolate_webhook_store)
    assert len(events) == 1
    event = events[0]
    assert event["key"] == "order-1"
    assert event["transmission_id"] == "update"
    assert event["status"] == "CANCELED"
    assert event["processed_at"] != first_processed_at


def test_record_respects_maximum_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "toss_webhook_events.json"
    monkeypatch.setattr(store, "_WEBHOOK_STATE_PATH", path)
    monkeypatch.setattr(store, "_MAX_RECORDED_EVENTS", 3)
    store._EVENT_CACHE = None  # type: ignore[attr-defined]
    store._EVENT_CACHE_PATH = None  # type: ignore[attr-defined]

    for idx in range(5):
        store.record_webhook_event(
            key=f"order-{idx}",
            transmission_id=f"trans-{idx}",
            order_id=f"order-{idx}",
            status="DONE",
            event_type="PAYMENT_STATUS_CHANGED",
        )

    events = _load_raw_events(path)
    assert len(events) == 3
    assert [event["key"] for event in events] == ["order-2", "order-3", "order-4"]
    store._EVENT_CACHE = None  # type: ignore[attr-defined]
    store._EVENT_CACHE_PATH = None  # type: ignore[attr-defined]


def test_record_ignored_when_key_missing(_isolate_webhook_store: Path) -> None:
    store.record_webhook_event(
        key=None,
        transmission_id="trans-0",
        order_id="order-0",
        status="DONE",
        event_type="PAYMENT_STATUS_CHANGED",
    )
    assert _isolate_webhook_store.exists() is False
    assert store.has_processed_webhook(None) is False
