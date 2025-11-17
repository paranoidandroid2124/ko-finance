import uuid
from datetime import datetime, timedelta, timezone

import pytest

import services.watchlist_digest_schedule_service as schedule_service


class DummySession:
    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _reset_store(tmp_path, monkeypatch):
    store_path = tmp_path / "digest_schedules.json"
    monkeypatch.setattr(schedule_service, "STORE_PATH", store_path)
    monkeypatch.setattr(schedule_service, "_CACHE", None)
    yield
    if store_path.exists():
        store_path.unlink()


def test_schedule_crud_flow():
    owner_filters = {"org_id": uuid.uuid4(), "user_id": None}
    schedule = schedule_service.create_schedule(
        label="오전 Digest",
        owner_filters=owner_filters,
        window_minutes=180,
        limit=25,
        time_of_day="09:30",
        timezone_name="Asia/Seoul",
        weekdays_only=False,
        slack_targets=["#digest"],
        email_targets=["ops@example.com"],
        enabled=True,
        actor="pytest",
    )

    schedules = schedule_service.list_schedules(owner_filters)
    assert len(schedules) == 1
    assert schedules[0]["label"] == "오전 Digest"

    schedule_id = uuid.UUID(schedule["id"])
    updated = schedule_service.update_schedule(
        schedule_id,
        owner_filters,
        label="업데이트 Digest",
        window_minutes=60,
        slack_targets=["#digest-updated"],
        email_targets=["team@example.com"],
        enabled=False,
        actor="pytest",
    )
    assert updated["label"] == "업데이트 Digest"
    assert updated["enabled"] is False

    due = schedule_service.list_due_schedules(now=datetime.now(timezone.utc) + timedelta(days=1))
    assert due, "schedule should be evaluated as due in the future"

    schedule_service.delete_schedule(schedule_id, owner_filters)
    assert schedule_service.list_schedules(owner_filters) == []


def test_mark_dispatched_updates_status(monkeypatch):
    owner_filters = {"org_id": None, "user_id": uuid.uuid4()}
    schedule = schedule_service.create_schedule(
        label="테스트",
        owner_filters=owner_filters,
        window_minutes=120,
        limit=10,
        time_of_day="06:00",
        timezone_name="UTC",
        weekdays_only=True,
        slack_targets=["#a"],
        email_targets=["a@example.com"],
        enabled=True,
        actor="pytest",
    )
    schedule_id = uuid.UUID(schedule["id"])
    scheduled_time = datetime.now(timezone.utc)
    schedule_service.mark_dispatched(
        schedule_id,
        dispatched_at=scheduled_time,
        next_run=scheduled_time + timedelta(days=1),
        status="success",
        last_error=None,
    )
    entries = schedule_service.load_schedule(schedule_id, owner_filters)
    assert entries is not None
    assert entries["last_status"] == "success"
    assert entries["last_error"] is None
