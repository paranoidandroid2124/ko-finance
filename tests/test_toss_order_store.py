from __future__ import annotations

from pathlib import Path

from services.payments import toss_order_store as store


def _tmp_path(tmp_path: Path) -> Path:
    return tmp_path / "toss_orders.json"


def test_record_and_retrieve_order(tmp_path: Path) -> None:
    store.reset_state_for_tests(path=_tmp_path(tmp_path))

    store.record_checkout(
        order_id="kfinance-pro-123",
        plan_tier="pro",
        amount=39000,
        currency="KRW",
        order_name="K-Finance Pro 플랜 구독",
        user_id="user-1",
        org_id="org-1",
        metadata={"redirectPath": "/settings"},
    )

    record = store.get_order("kfinance-pro-123")
    assert record is not None
    assert record.status == store.ORDER_STATUS_PENDING
    assert record.plan_tier == "pro"
    assert record.metadata["redirectPath"] == "/settings"


def test_update_order_status(tmp_path: Path) -> None:
    store.reset_state_for_tests(path=_tmp_path(tmp_path))
    store.record_checkout(
        order_id="order-xyz",
        plan_tier="starter",
        amount=9900,
        currency="KRW",
        order_name="Starter 업그레이드",
        user_id=None,
        org_id=None,
        metadata=None,
    )

    updated = store.update_order_status(
        "order-xyz",
        store.ORDER_STATUS_CONFIRMED,
        metadata={"paymentKey": "pay_123"},
    )
    assert updated is not None
    assert updated.status == store.ORDER_STATUS_CONFIRMED
    assert updated.metadata["paymentKey"] == "pay_123"


def test_update_order_status_creates_entry_with_defaults(tmp_path: Path) -> None:
    store.reset_state_for_tests(path=_tmp_path(tmp_path))

    created = store.update_order_status(
        "new-order",
        store.ORDER_STATUS_PAID,
        defaults={
            "plan_tier": "pro",
            "amount": 100,
            "currency": "KRW",
            "order_name": "Pro 업그레이드",
            "metadata": {"source": "test"},
        },
    )
    assert created is not None
    assert store.get_order("new-order") is not None
    assert created.metadata["source"] == "test"
