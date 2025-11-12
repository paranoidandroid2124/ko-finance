from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from services.payments import order_context_store as store


@pytest.fixture()
def temp_store(tmp_path: Path):
    store.reset_state_for_tests(path=tmp_path / "contexts.json")
    yield
    store.reset_state_for_tests()


def test_record_and_fetch_context(temp_store: None) -> None:
    org_id = str(uuid4())
    user_id = str(uuid4())
    store.record_order_context(order_id="order-a", org_id=org_id, plan_slug="starter", user_id=user_id)
    context = store.get_order_context("order-a")
    assert context is not None
    assert context.org_id == org_id
    assert context.plan_slug == "starter"
    assert context.user_id == user_id


def test_pop_removes_context(temp_store: None) -> None:
    store.record_order_context(order_id="order-b", org_id=None, plan_slug="pro", user_id=None)
    popped = store.pop_order_context("order-b")
    assert popped is not None
    assert store.get_order_context("order-b") is None


def test_prunes_expired_entries(tmp_path: Path) -> None:
    path = tmp_path / "contexts.json"
    store.reset_state_for_tests(path=path)
    store.record_order_context(order_id="order-expired", org_id=None, plan_slug=None, user_id=None)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["contexts"][0]["created_at"] = "1999-01-01T00:00:00+00:00"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    store.reset_state_for_tests(path=path)
    store.record_order_context(order_id="order-new", org_id=None, plan_slug=None, user_id=None)
    assert store.get_order_context("order-expired") is None
    assert store.get_order_context("order-new") is not None
    store.reset_state_for_tests()
