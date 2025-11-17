from datetime import datetime, timezone
import uuid

import pytest

import parse.tasks as tasks


class DummySession:
    def close(self) -> None:  # pragma: no cover - trivial
        pass


class DummyPlan:
    memory_digest_enabled = True
    memory_watchlist_enabled = True


class DisabledPlan:
    memory_digest_enabled = False
    memory_watchlist_enabled = False


def _make_schedule(**overrides):
    payload = {
        "id": str(uuid.uuid4()),
        "window_minutes": 60,
        "limit": 10,
        "time_of_day": "09:00",
        "timezone": "UTC",
        "weekdays_only": False,
        "slack_targets": ["#ops"],
        "email_targets": [],
        "enabled": True,
    }
    payload.update(overrides)
    return payload


def test_run_watchlist_digest_schedules_dispatch(monkeypatch):
    schedule = _make_schedule()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(tasks.watchlist_digest_schedule_service, "list_due_schedules", lambda now=None: [schedule])
    dispatch_calls = []
    monkeypatch.setattr(
        tasks.watchlist_service,
        "dispatch_watchlist_digest",
        lambda *args, **kwargs: dispatch_calls.append(kwargs),
    )
    mark_calls = []

    def fake_mark(*args, **kwargs):
        mark_calls.append((args, kwargs))

    monkeypatch.setattr(tasks.watchlist_digest_schedule_service, "mark_dispatched", fake_mark)
    monkeypatch.setattr(tasks.plan_service, "get_active_plan_context", lambda: DummyPlan())
    run_history = []
    monkeypatch.setattr(tasks.admin_ops_service, "append_run_history", lambda **kwargs: run_history.append(kwargs))

    result = tasks.run_watchlist_digest_schedules(now_iso="2025-01-01T00:00:00+00:00")
    assert result.startswith("dispatched:")
    assert dispatch_calls, "dispatch should be triggered"
    assert mark_calls and mark_calls[0][0][0] == uuid.UUID(schedule["id"])
    assert run_history[-1]["status"] == "completed"


def test_run_watchlist_digest_schedules_disabled(monkeypatch):
    schedule = _make_schedule()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(tasks.watchlist_digest_schedule_service, "list_due_schedules", lambda now=None: [schedule])
    monkeypatch.setattr(tasks.plan_service, "get_active_plan_context", lambda: DisabledPlan())
    mark_calls = []
    monkeypatch.setattr(
        tasks.watchlist_digest_schedule_service,
        "mark_dispatched",
        lambda *args, **kwargs: mark_calls.append(kwargs.get("status")),
    )
    monkeypatch.setattr(tasks.admin_ops_service, "append_run_history", lambda **kwargs: None)

    result = tasks.run_watchlist_digest_schedules()
    assert result == "digest_disabled"
    assert any(status == "skipped" for status in mark_calls)
