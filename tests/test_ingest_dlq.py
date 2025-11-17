from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from parse import tasks as parse_tasks
from services.ingest_errors import FatalIngestError


class _DummyTask:
    name = "m1.process_filing"
    request = SimpleNamespace(retries=4)

    def retry(self, *args, **kwargs):  # pragma: no cover - should not be called in this test
        raise AssertionError("retry should not be invoked for fatal errors")


def test_handle_ingest_exception_records_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    letter_id = uuid.uuid4()
    letter = SimpleNamespace(id=letter_id, payload={"filing_id": "test-filing"})

    recorded_letters: list[dict] = []

    def fake_record_dead_letter(*args, **kwargs):
        recorded_letters.append(kwargs)
        return letter

    audit_calls: list[dict] = []

    def fake_audit_ingest_event(**kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(parse_tasks.ingest_dlq_service, "record_dead_letter", fake_record_dead_letter)
    monkeypatch.setattr(parse_tasks, "audit_ingest_event", fake_audit_ingest_event)

    with pytest.raises(FatalIngestError):
        parse_tasks._handle_ingest_exception(
            _DummyTask(),
            FatalIngestError("boom"),
            payload={"filing_id": "test-filing"},
            receipt_no="RCP9001",
            corp_code="00123456",
            ticker="005930",
        )

    assert recorded_letters, "dead-letter entry should be recorded"
    assert audit_calls, "audit log should capture DLQ event"
    audit_entry = audit_calls[0]
    assert audit_entry["action"] == "ingest.dlq"
    assert audit_entry["target_id"] == "RCP9001"
    extra = audit_entry["extra"]
    assert extra["task"] == "m1.process_filing"
    assert extra["dlq_id"] == str(letter_id)
    assert extra["corp_code"] == "00123456"
    assert extra["ticker"] == "005930"
    assert extra["payload"] == {"filing_id": "test-filing"}
