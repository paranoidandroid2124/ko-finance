import sys
import types

sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore

from fastapi import FastAPI
from fastapi.testclient import TestClient

from types import SimpleNamespace
import uuid

from llm import llm_service
from llm.guardrails import SAFE_MESSAGE
from services import chat_service, vector_service
from services.vector_service import VectorSearchResult
from web.routers import rag

app = FastAPI()
app.include_router(rag.router, prefix="/api/v1")

client = TestClient(app)



def test_rag_query_guardrail(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "classify_query_intent",
        lambda question: {"decision": "pass", "reason": "", "model_used": "intent-test"},
    )
    context = [{"id": "c1", "type": "text", "content": "dummy"}]
    monkeypatch.setattr(
        vector_service,
        "query_vector_store",
        lambda **_: VectorSearchResult(filing_id="abc", chunks=context, related_filings=[]),
    )

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
    monkeypatch.setattr(
        llm_service,
        "classify_query_intent",
        lambda question: {"decision": "pass", "reason": "", "model_used": "intent-test"},
    )
    monkeypatch.setattr(
        vector_service,
        "query_vector_store",
        lambda **_: VectorSearchResult(filing_id="abc", chunks=[], related_filings=[]),
    )
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



def test_rag_query_intent_semipass(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "classify_query_intent",
        lambda question: {"decision": "semi_pass", "reason": "chit-chat", "model_used": "intent-test"},
    )

    def fail_query(**_kwargs):
        raise AssertionError("vector search should not be called")

    monkeypatch.setattr(vector_service, "query_vector_store", fail_query)
    monkeypatch.setattr(llm_service, "answer_with_rag", fail_query)
    monkeypatch.setattr(rag.run_rag_self_check, "delay", lambda payload: payload)

    dummy_session = SimpleNamespace(
        id=str(uuid.uuid4()),
        context_type="custom",
        context_id=None,
        memory_snapshot=None,
        user_id=None,
        org_id=None,
        archived_at=None,
    )
    monkeypatch.setattr(
        rag,
        "_resolve_session",
        lambda db, session_id=None, user_id=None, org_id=None, filing_id=None: dummy_session,
    )
    monkeypatch.setattr(
        chat_service,
        "build_conversation_memory",
        lambda db, session, recent_turn_limit=None: None,
    )
    monkeypatch.setattr(
        chat_service,
        "should_trigger_summary",
        lambda db, session, trigger_messages=None: False,
    )
    monkeypatch.setattr(chat_service, "enqueue_session_summary", lambda session_id: None)

    def fake_create_chat_message(db, message_id, session_id, role, content, turn_id, **kwargs):
        return SimpleNamespace(
            id=message_id or str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            turn_id=turn_id,
            meta=kwargs.get("meta") or {},
        )

    monkeypatch.setattr(chat_service, "create_chat_message", fake_create_chat_message)
    monkeypatch.setattr(chat_service, "update_message_state", lambda db, message_id, state, **kwargs: None)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "너는 누구니?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == ["intent_filter:semi_pass"]
    assert "공시·금융" in payload["answer"]
