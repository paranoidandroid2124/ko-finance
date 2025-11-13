from ingest import legal_guard
from ingest.file_downloader import attempt_viewer_fallback
from models.ingest_viewer_flag import IngestViewerFlag


def _stub_legal_meta(url: str) -> dict:
    return {
        "viewer_url": url,
        "viewer_path": "/dsaf001/main.do",
        "robots_allowed": True,
        "robots_checked": True,
        "robots_checked_at": "2025-01-01T00:00:00Z",
        "robots_cache_expires_at": "2025-01-01T01:00:00Z",
        "tos_checked": True,
        "tos_checked_at": "2025-01-01T00:00:00Z",
        "tos_version": "test",
        "cache_hit": False,
    }


def test_evaluate_viewer_access_cache(monkeypatch):
    legal_guard.reset_legal_cache()
    monkeypatch.setattr(legal_guard, "ROBOTS_TTL_SECONDS", 120)
    parser_calls = {"count": 0}

    class DummyParser:
        def can_fetch(self, ua, url):
            return True

    def fake_parser(now):
        parser_calls["count"] += 1
        return DummyParser()

    monkeypatch.setattr(legal_guard, "_ensure_robot_parser", fake_parser)
    first = legal_guard.evaluate_viewer_access(
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1",
        now=0,
        force_refresh=True,
    )
    assert first["cache_hit"] is False
    second = legal_guard.evaluate_viewer_access(
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1",
        now=10,
    )
    assert second["cache_hit"] is True
    assert parser_calls["count"] == 1


def test_attempt_viewer_fallback_blocked_by_flag(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("INGEST_VIEWER_FALLBACK", "true")
    monkeypatch.setenv("LEGAL_LOG", "true")
    db_session.add(
        IngestViewerFlag(
            corp_code="00112233",
            fallback_enabled=False,
            reason="Robots hold",
            updated_by="ops",
        )
    )
    db_session.commit()

    audit_calls = []

    def _audit(**kwargs):
        audit_calls.append(kwargs)

    def _fail_fetcher(*_args, **_kwargs):
        raise AssertionError("viewer_fetcher must not run when blocked.")

    result = attempt_viewer_fallback(
        receipt_no="202300000001",
        viewer_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202300000001",
        save_dir=str(tmp_path),
        corp_code="00112233",
        corp_name="ACME Inc.",
        db=db_session,
        viewer_fetcher=_fail_fetcher,
        legal_evaluator=_stub_legal_meta,
        audit_logger=_audit,
    )

    assert result.package is None
    assert result.status == "fallback_blocked"
    assert result.blocked is True
    assert audit_calls
    assert audit_calls[0]["action"] == "ingest.viewer_fallback"
    assert audit_calls[0]["extra"]["blocked"] is True


def test_attempt_viewer_fallback_success(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("INGEST_VIEWER_FALLBACK", "true")
    monkeypatch.setenv("LEGAL_LOG", "true")

    audit_calls = []

    def _audit(**kwargs):
        audit_calls.append(kwargs)

    package_stub = {
        "rcp_no": "202300000002",
        "download_url": "https://dart.fss.or.kr/download.zip",
        "pdf": str(tmp_path / "stub.pdf"),
        "xml": [],
        "attachments": [],
    }

    result = attempt_viewer_fallback(
        receipt_no="202300000002",
        viewer_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202300000002",
        save_dir=str(tmp_path),
        corp_code="00445566",
        corp_name="Bravo Corp",
        db=db_session,
        viewer_fetcher=lambda _url, _save: package_stub,
        legal_evaluator=_stub_legal_meta,
        audit_logger=_audit,
    )

    assert result.package == package_stub
    assert result.status == "fallback_success"
    assert result.blocked is False
    assert audit_calls
    assert audit_calls[0]["action"] == "ingest.viewer_fallback"
    assert audit_calls[0]["extra"]["blocked"] is False


def test_attempt_viewer_fallback_failure(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("INGEST_VIEWER_FALLBACK", "true")
    monkeypatch.setenv("LEGAL_LOG", "true")

    audit_calls = []

    def _audit(**kwargs):
        audit_calls.append(kwargs)

    result = attempt_viewer_fallback(
        receipt_no="202300000003",
        viewer_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202300000003",
        save_dir=str(tmp_path),
        corp_code="00778899",
        corp_name="Charlie",
        db=db_session,
        viewer_fetcher=lambda *_args, **_kwargs: None,
        legal_evaluator=_stub_legal_meta,
        audit_logger=_audit,
    )

    assert result.package is None
    assert result.status == "fallback_failure"
    assert result.blocked is False
    assert len(audit_calls) == 2  # attempt + failure
    assert audit_calls[-1]["action"] == "ingest.viewer_fallback_failed"
