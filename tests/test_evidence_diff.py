from datetime import datetime, timezone
from types import SimpleNamespace

from services import evidence_service


def test_attach_diff_metadata_includes_removed(monkeypatch):
    current_items = [{"urn_id": "urn:current", "quote": "current"}]

    removed_snapshot = SimpleNamespace(
        urn_id="urn:removed",
        payload={"urn_id": "urn:removed", "quote": "old"},
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    monkeypatch.setattr(evidence_service, "_load_latest_snapshots", lambda db, urns: {})
    monkeypatch.setattr(
        evidence_service,
        "_load_trace_removed_snapshots",
        lambda db, trace_id, current_urns: [removed_snapshot] if trace_id == "trace-1" else [],
    )
    monkeypatch.setattr(evidence_service, "_attach_document_metadata", lambda db, entries: None)
    monkeypatch.setattr(evidence_service, "_attach_table_metadata", lambda db, entries: None)

    diff_meta = evidence_service.attach_diff_metadata(
        db=None,
        evidence_items=current_items,
        trace_id="trace-1",
    )

    assert diff_meta["enabled"] is True
    assert diff_meta["removed"]
    removed = diff_meta["removed"][0]
    assert removed["urn_id"] == "urn:removed"
    assert removed["diff_type"] == "removed"
