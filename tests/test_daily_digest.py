import sys
import types
import unittest
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

    def test_send_filing_digest_sends_when_filings_exist(self):
        # Happy path should build the payload, send once, and mark completion.
        session = MagicMock()
        filings = [
            types.SimpleNamespace(corp_name="삼성전자", report_name="분기보고서", title=None, ticker="005930"),
            types.SimpleNamespace(corp_name="SK하이닉스", report_name="주요사항보고", title=None, ticker="000660"),
        ]

        with patch("parse.tasks._open_session", return_value=session), patch(
            "parse.tasks._check_digest_sent", return_value=False
        ), patch("parse.tasks._load_digest_filings", return_value=(5, filings)) as mock_load, patch(
            "parse.tasks.send_telegram_alert", return_value=True
        ) as mock_send, patch("parse.tasks._mark_digest_sent") as mock_mark:
            result = send_filing_digest("2025-01-24T18:00:00")

        self.assertEqual(result, "sent")
        mock_load.assert_called_once()
        mock_send.assert_called_once()
        sent_message = mock_send.call_args[0][0]
        self.assertIn("- 삼성전자: 분기보고서", sent_message)
        self.assertIn("...외 3건", sent_message)
        mock_mark.assert_called_once()
        session.close.assert_called_once()

    def test_send_filing_digest_sends_when_no_filings(self):
        # Even without filings the digest should fire once to keep the cadence.
        session = MagicMock()

        with patch("parse.tasks._open_session", return_value=session), patch(
            "parse.tasks._check_digest_sent", return_value=False
        ), patch("parse.tasks._load_digest_filings", return_value=(0, [])), patch(
            "parse.tasks.send_telegram_alert", return_value=True
        ) as mock_send, patch("parse.tasks._mark_digest_sent") as mock_mark:
            result = send_filing_digest("2025-01-23")

        self.assertEqual(result, "sent")
        mock_send.assert_called_once()
        sent_message = mock_send.call_args[0][0]
        self.assertIn("오늘 등록된 공시: 0건", sent_message)
        mock_mark.assert_called_once()
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
