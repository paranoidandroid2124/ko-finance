﻿import json
import sys
import types
import unittest
from unittest.mock import patch


class _DummyLangfuse:
    def __init__(self, *_, **__):
        pass

    def trace(self, *_, **__):
        class _Trace:
            def generation(self, *_, **__):
                return None

            def update(self, *_, **__):
                return None

        return _Trace()

    def flush(self):
        return None


sys.modules.setdefault("langfuse", types.SimpleNamespace(Langfuse=_DummyLangfuse))  # type: ignore

import llm.llm_service as llm_service
from llm.guardrails import SAFE_MESSAGE


class JsonCompletionTests(unittest.TestCase):
    def test_fallback_model_used_on_primary_failure(self):
        class DummyMessage:
            def __init__(self, content):
                self.content = content

        class DummyChoice:
            def __init__(self, content):
                self.message = DummyMessage(content)

        class DummyResponse:
            def __init__(self, content):
                self.choices = [DummyChoice(content)]

        def completion_side_effect(model, messages, response_format=None):
            if model == llm_service.CLASSIFICATION_MODEL:
                raise RuntimeError("primary failure")
            return DummyResponse(json.dumps({"category": "Test", "confidence_score": 0.9}))

        with patch("llm.llm_service.litellm.completion", side_effect=completion_side_effect):
            result = llm_service.classify_filing_content("sample text")

        self.assertEqual(result["category"], "Test")
        self.assertEqual(result["confidence_score"], 0.9)

    def test_json_decode_error_returns_error(self):
        class DummyMessage:
            def __init__(self, content):
                self.content = content

        class DummyChoice:
            def __init__(self, content):
                self.message = DummyMessage(content)

        class DummyResponse:
            def __init__(self, content):
                self.choices = [DummyChoice(content)]

        with patch(
            "llm.llm_service.litellm.completion",
            return_value=DummyResponse("not-json"),
        ):
            result = llm_service.classify_filing_content("sample text")

        self.assertIn("error", result)
        self.assertIn("JSON decode failure", result["error"])


class NewsAnalysisValidationTests(unittest.TestCase):
    def test_validate_news_analysis_success(self):
        raw = {
            "sentiment": "0.8",
            "topics": ["AI", {"topic": "Market"}],
            "rationale": ["First line", "Second line"],
        }
        result = llm_service.validate_news_analysis_result(raw)

        self.assertTrue(result["validated"])
        self.assertAlmostEqual(result["sentiment"], 0.8)
        self.assertEqual(result["topics"], ["AI", "Market"])
        self.assertEqual(result["rationale"], "First line\nSecond line")
        self.assertFalse(result.get("validation_warnings"))

    def test_validate_news_analysis_clamps_and_warns(self):
        raw = {
            "sentiment": 1.5,
            "topics": "AI, Market",
            "rationale": "Single rationale",
        }
        result = llm_service.validate_news_analysis_result(raw)

        self.assertTrue(result["validated"])
        self.assertAlmostEqual(result["sentiment"], 1.0)
        self.assertEqual(result["topics"], ["AI", "Market"])
        self.assertEqual(result["rationale"], "Single rationale")
        warnings = result.get("validation_warnings")
        self.assertIsNotNone(warnings)
        self.assertTrue(any("clamped" in message for message in warnings))

    def test_validate_news_analysis_missing_sentiment_error(self):
        raw = {
            "topics": ["AI"],
            "rationale": ["Reason"],
        }
        result = llm_service.validate_news_analysis_result(raw)

        self.assertIn("error", result)
        self.assertTrue(any("sentiment" in detail for detail in result.get("details", [])))


class RagCitationHelperTests(unittest.TestCase):
    def test_select_prompt_builder_for_table(self):
        context = [{"type": "table"}, {"type": "text"}]
        builder = llm_service._select_prompt_builder(context)
        from llm.prompts import table_aware_rag, rag_qa  # local import for comparison

        self.assertIs(builder, table_aware_rag)
        builder_text = llm_service._select_prompt_builder([{"type": "text"}])
        self.assertIs(builder_text, rag_qa)

    def test_categorize_context(self):
        context = [
            {"type": "table", "page_number": 3},
            {"type": "footnote"},
            {"type": "text"},
        ]
        categorized = llm_service._categorize_context(context)
        self.assertTrue(categorized["page"])
        self.assertTrue(categorized["table"])
        self.assertTrue(categorized["footnote"])

    def test_extract_and_find_citations(self):
        answer = "Revenue increased (p.5) according to (Table 2, p.5) and see details (Footnote 1, p.5)."
        citations = llm_service._extract_citations(answer)
        self.assertTrue(citations["page"])
        self.assertTrue(citations["table"])
        self.assertTrue(citations["footnote"])

        required = {"page": True, "table": True, "footnote": True}
        missing = llm_service._find_missing_citations(required, citations)
        self.assertFalse(missing)

    def test_missing_citations_detected(self):
        required = {"page": True, "table": True, "footnote": False}
        citations = {"page": ["(p.3)"], "table": [], "footnote": []}
        missing = llm_service._find_missing_citations(required, citations)
        self.assertEqual(missing, ["table"])

    def test_collect_highlights_structure(self):
        context = [
            {"id": "chunk-1", "type": "table", "page_number": 2, "section": "table", "source": "pdf", "metadata": {"key": "value"}},
            {"id": "chunk-2", "type": "text"},
        ]
        highlights = llm_service._collect_highlights(context)
        self.assertEqual(len(highlights), 2)
        self.assertEqual(highlights[0]["chunk_id"], "chunk-1")
        self.assertEqual(highlights[0]["metadata"]["key"], "value")


class GuardrailEnforcementTests(unittest.TestCase):
    def test_guardrail_replaces_answer(self):
        context_chunks = [{"type": "text", "content": "dummy"}]

        class DummyMessage:
            def __init__(self, content: str):
                self.content = content

        dummy_response = types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=DummyMessage("Buy this stock now (p.1)"))]
        )

        with patch("llm.llm_service._safe_completion", return_value=(dummy_response, "test-model")):
            result = llm_service.answer_with_rag("question", context_chunks)

        self.assertTrue(any("guardrail_violation" in warn for warn in result["warnings"]))
        self.assertEqual(result["answer"], SAFE_MESSAGE)
        self.assertEqual(result["original_answer"], "Buy this stock now (p.1)")
        self.assertEqual(result["error"], result["warnings"][0])


if __name__ == "__main__":
    unittest.main()


