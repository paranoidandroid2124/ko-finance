import sys
import types

sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore

from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm import llm_service
from llm.guardrails import SAFE_MESSAGE
from services import vector_service
from web.routers import rag

app = FastAPI()
app.include_router(rag.router, prefix="/api/v1")

client = TestClient(app)


def test_rag_query_guardrail(monkeypatch):
    context = [{"id": "c1", "type": "text", "content": "dummy"}]
    monkeypatch.setattr(vector_service, "query_vector_store", lambda **_: context)

    def fake_answer(question, context_chunks):
        return {
            "answer": SAFE_MESSAGE,
            "context": context_chunks,
            "citations": {"page": ["(p.1)"]},
            "warnings": ["guardrail_violation:buy\\s+this\\s+stock"],
            "highlights": [],
            "error": "guardrail_violation:buy\\s+this\\s+stock",
            "original_answer": "Buy this stock now (p.1)",
            "model_used": "test-model",
        }

    monkeypatch.setattr(llm_service, "answer_with_rag", fake_answer)
    monkeypatch.setattr(rag.run_rag_self_check, "delay", lambda payload: payload)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "샘플 질문", "filing_id": "abc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("투자 자문이나 매수·매도 권고는 제공되지 않습니다")
    assert payload["error"].startswith("guardrail_violation")
    assert payload["original_answer"] == "Buy this stock now (p.1)"
    assert payload["model_used"] == "test-model"
    assert payload["warnings"] == ["guardrail_violation:buy\\s+this\\s+stock"]


def test_rag_query_no_context(monkeypatch):
    monkeypatch.setattr(vector_service, "query_vector_store", lambda **_: [])
    monkeypatch.setattr(rag.run_rag_self_check, "delay", lambda payload: payload)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "샘플 질문", "filing_id": "abc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == ["no_context"]
    assert payload["context"] == []
    assert payload["answer"] == "관련 근거 문서를 찾지 못했습니다. 다른 질문을 시도해 주세요."
