from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Dict

import pytest

from services import event_brief_service, report_renderer
from services.evidence_package import make_evidence_bundle


def test_make_event_brief_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        event_brief_service.admin_ui_service,
        "load_ui_settings",
        lambda: {
            "theme": {"primaryColor": "#123456", "accentColor": "#654321"},
            "copy": {"welcomeSubcopy": "따뜻한 금융 연구를 돕습니다."},
        },
    )

    task_payload: Dict[str, Any] = {
        "taskId": "task-001",
        "actor": "ops-admin",
        "scope": "filings,news",
        "status": "completed",
        "durationMs": 4200,
        "queueWaitMs": 800,
        "totalElapsedMs": 5000,
    }
    diff_payload = {"created": 1, "updated": 2, "removed": 0, "totalChanges": 3}
    brief = event_brief_service.make_event_brief(task=task_payload, diff=diff_payload, sla_target_ms=1800000)
    payload = event_brief_service.event_brief_to_dict(brief)

    assert payload["report"]["taskId"] == "task-001"
    assert payload["rag"]["status"] == "completed"
    assert any("Evidence 변경" in highlight for highlight in payload["summary"]["highlights"])
    assert payload["report"]["brand"]["primaryColor"] == "#123456"


def test_render_event_brief_with_latex(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "event_brief.pdf"

    def fake_compile(tex_path: Path) -> Path:
        output_pdf = tex_path.with_suffix(".pdf")
        output_pdf.write_bytes(b"%PDF-1.4 fake")
        return output_pdf

    monkeypatch.setattr(report_renderer, "compile_latex_pdf", fake_compile)

    context = {"report": {"taskId": "task-002"}, "summary": {"overview": "테스트"}}
    result = report_renderer.render_event_brief(context, output_path=output_path)

    assert result == output_path
    assert output_path.exists()


def test_make_evidence_bundle_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EVENT_BRIEF_OUTPUT_DIR", str(tmp_path / "bundles"))
    monkeypatch.setattr("services.storage_service.is_enabled", lambda: False)

    pdf_input = tmp_path / "input.pdf"
    pdf_input.write_bytes(b"%PDF-1.4 stub")

    brief_payload = {"report": {"taskId": "task-003"}}
    diff_payload = {"created": 0, "updated": 0, "removed": 0}
    trace_payload = {"trace_id": "trace-xyz"}
    audit_payload = {"log_key": "audit-xyz"}

    package = make_evidence_bundle(
        task_id="task-003",
        pdf_path=pdf_input,
        brief_payload=brief_payload,
        diff_payload=diff_payload,
        trace_payload=trace_payload,
        audit_payload=audit_payload,
    )

    assert package.pdf_object is None
    assert package.zip_object is None
    assert package.pdf_path.exists()
    assert package.zip_path.exists()
    assert package.manifest_path.exists()

    with zipfile.ZipFile(package.zip_path) as archive:
        names = set(archive.namelist())
        assert "event_brief.pdf" in names
        assert "event_brief.json" in names
        assert "manifest.json" in names

    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    assert manifest["taskId"] == "task-003"


def test_make_evidence_bundle_custom_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EVENT_BRIEF_OUTPUT_DIR", str(tmp_path / "bundles"))
    monkeypatch.setattr("services.storage_service.is_enabled", lambda: False)

    pdf_input = tmp_path / "input.pdf"
    pdf_input.write_bytes(b"%PDF-1.4 stub")

    package = make_evidence_bundle(
        task_id="task-004",
        pdf_path=pdf_input,
        brief_payload={"report": {"title": "Custom"}},
        pdf_filename="event_study_report.pdf",
        payload_filename="event_study_report.json",
    )

    assert package.pdf_path.name == "event_study_report.pdf"
    with zipfile.ZipFile(package.zip_path) as archive:
        names = set(archive.namelist())
        assert "event_study_report.pdf" in names
        assert "event_study_report.json" in names


def test_render_event_study_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "event_study.pdf"

    def fake_compile(tex_path: Path) -> Path:
        pdf_file = tex_path.with_suffix(".pdf")
        pdf_file.write_bytes(b"%PDF-1.4 stub")
        return pdf_file

    monkeypatch.setattr(report_renderer, "compile_latex_pdf", fake_compile)

    context = {
        "report": {"title": "Event Study Report", "generatedAt": "2025-01-01T00:00:00Z", "requestedBy": "qa"},
        "filters": {
            "windowLabel": "[-5,20]",
            "eventTypesLabel": "BUYBACK",
            "marketsLabel": "KOSPI",
            "capBucketsLabel": "ALL",
            "dateRangeLabel": "최근",
            "searchLabel": "—",
        },
        "metrics": {
            "sampleSize": 10,
            "weightedMeanCaar": "+1.20%",
            "weightedHitRate": "55.0%",
            "weightedPValue": "0.0300",
            "windowEnd": 20,
        },
        "summary": [
            {
                "eventTypeLabel": "BUYBACK",
                "sampleSize": 10,
                "meanCaarLabel": "+1.20%",
                "hitRateLabel": "55.0%",
                "pValueLabel": "0.0300",
            }
        ],
        "events": {
            "rows": [
                {
                    "corpName": "삼성전자",
                    "ticker": "005930",
                    "eventType": "BUYBACK",
                    "caarLabel": "+1.20%",
                    "viewerUrl": "https://example.com",
                    "eventDateLabel": "2025-01-03",
                    "marketLabel": "KOSPI",
                    "marketCapLabel": "5,000,000,000,000",
                }
            ]
        },
        "series": [{"eventType": "BUYBACK", "windowEndValue": "+1.20%"}],
        "highlights": {
            "topPositive": {"text": "삼성전자 (005930) • BUYBACK • +1.20%", "viewerUrl": "https://example.com"},
            "topNegative": {"text": "데이터 없음", "viewerUrl": None},
        },
    }

    result = report_renderer.render_event_study_report(context, output_path=output_path)
    assert result == output_path
    assert output_path.exists()
