import sys
import types
import unittest
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

# Stub PyMuPDF dependency required by parse.tasks import.
sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore

from parse.tasks import _build_digest_message, send_filing_digest


class DailyDigestTaskTests(unittest.TestCase):
    def test_send_filing_digest_skips_weekend(self):
        # Weekend input should short-circuit before touching the database.
        result = send_filing_digest("2025-01-25")
        self.assertEqual(result, "skipped_weekend")

    def test_send_filing_digest_skips_duplicate(self):
        # Duplicate guard must prevent a second send for the same date.
        session = MagicMock()
        with patch("parse.tasks._open_session", return_value=session), patch(
            "parse.tasks._check_digest_sent", return_value=True
        ) as mock_check:
            result = send_filing_digest("2025-01-24")

        self.assertEqual(result, "skipped_duplicate")
        mock_check.assert_called_once()
        session.close.assert_called_once()

    def test_send_filing_digest_uses_preview_payload(self):
        # Preview pipeline should build and send the digest message.
        session = MagicMock()
        preview_payload = {
            "timeframe": "daily",
            "periodLabel": "2025-01-24 · 오늘의 다이제스트",
            "generatedAtLabel": "2025-01-24 09:00 (KST)",
            "news": [{"headline": "주요 뉴스", "summary": "요약", "source": "Yonhap"}],
            "watchlist": [{"title": "005930", "description": "워치리스트", "changeLabel": "Sentiment +0.2"}],
            "sentiment": {"summary": "긍정 3건 · 중립 1건 · 부정 0건", "scoreLabel": "72/100", "trend": "up"},
            "actions": [{"title": "워치리스트 점검", "note": "새 알림 확인"}],
            "llmOverview": "LLM Insight",
            "llmPersonalNote": "개인 메모",
        }
        plan_context = types.SimpleNamespace(memory_digest_enabled=True)
        user_settings = types.SimpleNamespace(enabled=True, digest=True)
        default_user = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

        with patch("parse.tasks._open_session", return_value=session), patch(
            "parse.tasks._check_digest_sent", return_value=False
        ), patch("parse.tasks.plan_service.get_active_plan_context", return_value=plan_context), patch(
            "parse.tasks.lightmem_gate.default_user_id", return_value=default_user
        ), patch(
            "parse.tasks.lightmem_gate.load_user_settings", return_value=user_settings
        ), patch(
            "parse.tasks.lightmem_gate.digest_enabled", return_value=True
        ), patch(
            "parse.tasks.build_digest_preview", return_value=preview_payload
        ) as mock_preview, patch(
            "parse.tasks._load_digest_filings"
        ) as mock_load, patch(
            "parse.tasks.send_telegram_alert", return_value=True
        ) as mock_send, patch(
            "parse.tasks._mark_digest_sent"
        ) as mock_mark, patch(
            "parse.tasks.digest_snapshot_service.upsert_snapshot"
        ) as mock_snapshot:
            result = send_filing_digest("2025-01-24T18:00:00")

        self.assertEqual(result, "sent")
        mock_preview.assert_called_once()
        mock_load.assert_not_called()
        mock_send.assert_called_once()
        sent_message = mock_send.call_args[0][0]
        self.assertIn("뉴스 하이라이트", sent_message)
        self.assertIn("워치리스트 업데이트", sent_message)
        self.assertIn("LLM Insight", sent_message)
        mock_mark.assert_called_once()
        mock_snapshot.assert_called_once()
        session.close.assert_called_once()

    def test_send_filing_digest_falls_back_when_preview_fails(self):
        # Preview failures should fall back to the filings summary.
        session = MagicMock()
        filings = [
            types.SimpleNamespace(corp_name="삼성전자", report_name="분기보고서", title=None, ticker="005930"),
            types.SimpleNamespace(corp_name="카카오", report_name=None, title="정정공시", ticker="035720"),
        ]
        plan_context = types.SimpleNamespace(memory_digest_enabled=False)

        with patch("parse.tasks._open_session", return_value=session), patch(
            "parse.tasks._check_digest_sent", return_value=False
        ), patch("parse.tasks.plan_service.get_active_plan_context", return_value=plan_context), patch(
            "parse.tasks.lightmem_gate.default_user_id", return_value=None
        ), patch(
            "parse.tasks.lightmem_gate.load_user_settings", return_value=None
        ), patch(
            "parse.tasks.lightmem_gate.digest_enabled", return_value=False
        ), patch(
            "parse.tasks.build_digest_preview", side_effect=RuntimeError("preview_failed")
        ), patch(
            "parse.tasks._load_digest_filings", return_value=(2, filings)
        ) as mock_load, patch(
            "parse.tasks.send_telegram_alert", return_value=True
        ) as mock_send, patch(
            "parse.tasks._mark_digest_sent"
        ) as mock_mark, patch(
            "parse.tasks.digest_snapshot_service.upsert_snapshot"
        ) as mock_snapshot:
            result = send_filing_digest("2025-01-24")

        self.assertEqual(result, "sent")
        mock_load.assert_called_once()
        sent_message = mock_send.call_args[0][0]
        self.assertIn("[일일 공시 요약]", sent_message)
        mock_mark.assert_called_once()
        mock_snapshot.assert_not_called()
        session.close.assert_called_once()

    def test_build_digest_message_formats(self):
        # Message builder should render header, bullet list, remainder, and link.
        filings = [
            types.SimpleNamespace(corp_name="삼성전자", report_name="분기보고서", title=None, ticker="005930"),
            types.SimpleNamespace(corp_name="카카오", report_name=None, title="정정공시", ticker="035720"),
        ]
        message = _build_digest_message(date(2025, 1, 24), 4, filings)
        self.assertIn("[일일 공시 요약] 2025-01-24", message)
        self.assertIn("- 삼성전자: 분기보고서", message)
        self.assertIn("- 카카오: 정정공시", message)
        self.assertIn("...외 2건", message)
        self.assertIn("?date=2025-01-24", message)


if __name__ == "__main__":
    unittest.main()
