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
    context = [
        {
            "id": "c1",
            "chunk_id": "chunk-1",
            "type": "text",
            "content": "Evidence quote",
            "page_number": 5,
            "section": "Overview",
            "metadata": {
                "paragraph_id": "para-500",
                "anchor": {
                    "paragraph_id": "para-500",
                    "pdf_rect": {"page": 5, "x": 120, "y": 340, "width": 380, "height": 64},
                    "similarity": 0.86,
                },
                "source_reliability": "high",
                "created_at": "2025-11-20T04:12:45Z",
            },
            "self_check": {"score": 0.78, "verdict": "pass", "explanation": "Matches original filing"},
            "score": 0.86,
        }
    ]
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
    monkeypatch.setattr(rag.snapshot_evidence_diff, "delay", lambda payload: payload)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "sample question", "filing_id": "abc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"].startswith("guardrail_violation")
    assert payload["original_answer"] == "Buy this stock now (p.1)"
    assert payload["model_used"] == "test-model"
    assert payload["warnings"] == ["guardrail_violation:buy\\s+this\\s+stock"]
    assert payload["meta"]["evidence_version"] == "v2"
    assert payload["context"]
    evidence = payload["context"][0]
    assert evidence["urn_id"].startswith("urn:chunk:")
    assert evidence["chunk_id"] == "chunk-1"
    assert evidence["quote"] == "Evidence quote"
    assert evidence["content"] == "Evidence quote"
    assert evidence["page_number"] == 5
    assert evidence["section"] == "Overview"
    assert evidence["self_check"]["verdict"] == "pass"
    assert evidence["source_reliability"] == "high"
    assert evidence["anchor"]["pdf_rect"]["page"] == 5

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
    monkeypatch.setattr(rag.snapshot_evidence_diff, "delay", lambda payload: payload)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "sample question", "filing_id": "abc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == ["no_context"]
    assert payload["context"] == []
    assert payload["answer"] == rag.NO_CONTEXT_ANSWER



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
    monkeypatch.setattr(rag.snapshot_evidence_diff, "delay", lambda payload: payload)

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
        json={"question": "ë„ˆëŠ” ëˆ„êµ¬ë‹ˆ?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == ["intent_filter:semi_pass"]
    assert payload["answer"] == rag.INTENT_GENERAL_MESSAGE
