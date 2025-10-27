import types

import parse.tasks as tasks


class DummySession:
    def __init__(self):
        self.committed = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.committed = False

    def close(self):
        self.closed = True


def test_snapshot_evidence_diff_dispatch(monkeypatch):
    dummy_session = DummySession()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: dummy_session)

    stored_records = [{"urn_id": "urn:chunk:1", "snapshot_hash": "hash-1", "diff_type": "created"}]

    def fake_persist(db, urn_id, evidence_payload, author, process):
        assert db is dummy_session
        assert urn_id == "urn:chunk:1"
        assert author == "tester"
        assert process == "api.rag.query"
        return stored_records[0]

    monkeypatch.setattr(tasks, "_persist_evidence_snapshot", fake_persist)

    result = tasks.snapshot_evidence_diff(
        {
            "trace_id": "trace-123",
            "author": "tester",
            "process": "api.rag.query",
            "evidence": [{"urn_id": "urn:chunk:1"}],
        }
    )

    assert result["stored"] == stored_records
    assert dummy_session.committed is True
    assert dummy_session.closed is True


def test_snapshot_evidence_diff_handles_errors(monkeypatch):
    dummy_session = DummySession()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: dummy_session)

    def raise_error(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(tasks, "_persist_evidence_snapshot", raise_error)

    result = tasks.snapshot_evidence_diff(
        {
            "trace_id": "trace-err",
            "author": None,
            "process": "api.rag.query",
            "evidence": [{"urn_id": "urn:chunk:2"}],
        }
    )

    assert "error" in result
    assert dummy_session.committed is False
    assert dummy_session.closed is True
