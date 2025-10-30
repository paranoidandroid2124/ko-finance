import json
from pathlib import Path

import pytest

from services.payments import toss_webhook_audit as audit


@pytest.fixture(autouse=True)
def _reset_audit_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "toss_webhook_audit.jsonl"
    monkeypatch.setattr(audit, "_AUDIT_LOG_PATH", path)
    monkeypatch.setattr(audit, "_MAX_PERSISTED_ENTRIES", 3)
    monkeypatch.setattr(audit, "SessionLocal", None)
    monkeypatch.setattr(audit, "TossWebhookEventLog", None)
    yield path
    if path.exists():
        path.unlink()


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def test_append_audit_entry_writes_jsonl(_reset_audit_log: Path) -> None:
    context = {"order_id": "order-1", "status": "DONE"}
    payload = {"data": {"status": "DONE"}}

    audit.append_webhook_audit_entry(result="processed", context=context, payload=payload, message="ok")

    lines = _read_lines(_reset_audit_log)
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["result"] == "processed"
    assert entry["message"] == "ok"
    assert entry["context"] == context
    assert entry["payload"] == payload
    assert "loggedAt" in entry


def test_read_recent_entries_returns_latest_first(_reset_audit_log: Path) -> None:
    for idx in range(5):
        audit.append_webhook_audit_entry(
            result=f"result-{idx}",
            context={"order_id": f"order-{idx}"},
        )

    entries = list(audit.read_recent_webhook_entries(limit=2))
    assert len(entries) == 2
    assert entries[0]["context"]["order_id"] == "order-4"
    assert entries[1]["context"]["order_id"] == "order-3"


def test_truncate_keeps_recent_entries_only(_reset_audit_log: Path) -> None:
    for idx in range(6):
        audit.append_webhook_audit_entry(
            result="processed",
            context={"order_id": f"order-{idx}"},
        )

    lines = _read_lines(_reset_audit_log)
    assert len(lines) == 3
    entries = [json.loads(line) for line in lines]
    assert [item["context"]["order_id"] for item in entries] == ["order-3", "order-4", "order-5"]
