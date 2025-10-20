import sys
import types

sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore

from parse import tasks


def test_summarize_rag_result_basic():
    question = "What is the revenue?"
    context_chunks = [{"id": "chunk1", "type": "table"}]
    answer_result = {
        "answer": "Revenue increased (p.1).",
        "citations": {"page": ["(p.1)"]},
        "warnings": ["notice"],
        "error": None,
        "model_used": "test-model",
    }

    metrics = tasks._summarize_rag_result(question, context_chunks, answer_result)

    assert metrics["question"] == question
    assert metrics["context_size"] == 1
    assert metrics["answer_length"] == len("Revenue increased (p.1).")
    assert metrics["citations"]["page"] == ["(p.1)"]
    assert metrics["warnings"] == ["notice"]
    assert metrics["model_used"] == "test-model"


def test_run_rag_self_check_returns_summary(monkeypatch):
    # Stub Langfuse so the task can run without the external dependency.
    monkeypatch.setattr(
        tasks.llm_service,
        "LANGFUSE_CLIENT",
        types.SimpleNamespace(trace=lambda **_: types.SimpleNamespace(generation=lambda **_: None), flush=lambda: None),
    )

    payload = {
        "question": "Sample question?",
        "filing_id": "filing-1",
        "answer": {
            "answer": "Sample answer",
            "warnings": [],
            "citations": {},
        },
        "context": [],
        "trace_id": "trace-123",
    }

    summary = tasks.run_rag_self_check(payload)

    assert summary["filing_id"] == "filing-1"
    assert summary["trace_id"] == "trace-123"
    assert summary["context_size"] == 0
    assert summary["answer_length"] == len("Sample answer")
