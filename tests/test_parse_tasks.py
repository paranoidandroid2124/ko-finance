import sys
import types
import unittest

# Stub PyMuPDF dependency required by parse.pdf_parser during import
sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore

from parse.tasks import _normalize_facts, _format_notification


class NormalizeFactPayloadsTests(unittest.TestCase):
    def test_returns_list_when_input_is_list_of_dicts(self):
        payload = [{"field": "amount", "value": 100}, {"field": "currency", "value": "KRW"}]
        normalized = _normalize_facts(payload)
        self.assertEqual(normalized, payload)

    def test_converts_dict_to_list(self):
        payload = {
            "amount": {"value": 100, "unit": "KRW"},
            "counterparty": {"value": "ABC"},
        }
        normalized = _normalize_facts(payload)
        self.assertEqual(
            normalized,
            [
                {"field": "amount", "value": 100, "unit": "KRW"},
                {"field": "counterparty", "value": "ABC"},
            ],
        )

    def test_filters_out_non_dict_entries(self):
        payload = [
            {"field": "amount", "value": 100},
            "invalid",
            123,
        ]
        normalized = _normalize_facts(payload)
        self.assertEqual(normalized, [{"field": "amount", "value": 100}])

    def test_handles_none(self):
        self.assertEqual(_normalize_facts(None), [])


if __name__ == "__main__":
    unittest.main()

class NotificationFormattingTests(unittest.TestCase):
    def test_format_notification_includes_ticker_and_link(self):
        filing = types.SimpleNamespace(
            ticker="005930",
            report_name="주요사항 보고",
            title=None,
            urls={"viewer": "http://example.com"},
        )
        summary = {"insight": "핵심 요약 문장이 들어갑니다"}
        message = _format_notification(filing, summary)
        self.assertIn("005930", message)
        self.assertIn("주요사항 보고", message)
        self.assertIn("핵심 요약", message)
        self.assertIn("http://example.com", message)
