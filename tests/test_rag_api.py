import sys
import types

sys.modules.setdefault("fitz", types.SimpleNamespace())  # type: ignore
sys.modules.setdefault(
    "pyotp",
    types.SimpleNamespace(
        TOTP=lambda *args, **kwargs: None,
        random_base32=lambda: "BASE32",
    ),
)  # type: ignore

fake_org_module = types.ModuleType("models.org")
fake_org_module.Org = type("Org", (), {})
fake_org_module.OrgRole = type("OrgRole", (), {})
fake_org_module.UserOrg = type("UserOrg", (), {})
sys.modules.setdefault("models.org", fake_org_module)

fake_plan_catalog_module = types.ModuleType("services.plan_catalog_service")
fake_plan_catalog_module.load_plan_catalog = lambda *_, **__: {}
fake_plan_catalog_module.update_plan_catalog = lambda *_, **__: None
sys.modules.setdefault("services.plan_catalog_service", fake_plan_catalog_module)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from types import SimpleNamespace
import uuid

from llm import llm_service
from llm.guardrails import SAFE_MESSAGE
from services import chat_service, vector_service
from services.vector_service import VectorSearchResult
import importlib

rag = importlib.import_module("web.routers.rag")

app = FastAPI()
app.include_router(rag.router, prefix="/api/v1")

client = TestClient(app)


def fake_diff_metadata(_db, evidence):
    for item in evidence:
        if isinstance(item, dict):
            item.setdefault("diff_type", "created")
            item.pop("previous_quote", None)
            item.pop("previousQuote", None)
            item.pop("previous_section", None)
            item.pop("previousSection", None)
            item.pop("previous_page_number", None)
            item.pop("previousPageNumber", None)
            item.pop("previous_anchor", None)
            item.pop("previousAnchor", None)
            item.pop("previous_source_reliability", None)
            item.pop("previousSourceReliability", None)
            item.pop("previous_self_check", None)
            item.pop("previousSelfCheck", None)
            item.pop("diff_changed_fields", None)
            item.pop("diffChangedFields", None)
    return {"enabled": bool(evidence), "removed": []}


class DummyTask:
    def delay(self, payload):
        return payload


def test_rag_query_guardrail(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "classify_query_intent",
        lambda question: {"decision": "pass", "reason": "", "model_used": "intent-test"},
    )
    monkeypatch.setattr(
        llm_service,
        "assess_query_risk",
        lambda question: {"decision": "pass", "rag_mode": "vector", "reason": None, "model_used": "judge-test"},
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

    def fake_answer(question, context_chunks, **_kwargs):
        return {
            "answer": SAFE_MESSAGE,
            "context": context_chunks,
            "citations": {
                "page": [
                    {
                        "label": "(p.5)",
                        "bucket": "page",
                        "chunk_id": "chunk-1",
                        "page_number": 5,
                        "char_start": 0,
                        "char_end": 64,
                        "sentence_hash": "hash-1",
                    }
                ]
            },
            "warnings": ["guardrail_violation:buy\\s+this\\s+stock"],
            "highlights": [],
            "error": "guardrail_violation:buy\\s+this\\s+stock",
            "original_answer": "Buy this stock now (p.1)",
            "model_used": "test-model",
            "rag_mode": "vector",
        }

    monkeypatch.setattr(llm_service, "generate_rag_answer", fake_answer)
    monkeypatch.setattr(rag, "run_rag_self_check", DummyTask())
    monkeypatch.setattr(rag, "snapshot_evidence_diff", DummyTask())
    monkeypatch.setattr(rag, "attach_diff_metadata", fake_diff_metadata)
    monkeypatch.setattr(rag, "_enqueue_evidence_snapshot", lambda *args, **kwargs: None)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "sample question", "filing_id": "abc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rag_mode"] == "vector"
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
    assert evidence["diff_type"] == "created"
    assert not evidence.get("previous_quote")
    assert payload["meta"]["evidence_diff"] == {"enabled": True, "removed": []}
    assert payload["citations"]["page"][0]["page_number"] == 5
    assert payload["citations"]["page"][0]["sentence_hash"] == "hash-1"

def test_rag_query_no_context(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "classify_query_intent",
        lambda question: {"decision": "pass", "reason": "", "model_used": "intent-test"},
    )
    monkeypatch.setattr(
        llm_service,
        "assess_query_risk",
        lambda question: {"decision": "pass", "rag_mode": "vector", "reason": None, "model_used": "judge-test"},
    )
    monkeypatch.setattr(
        vector_service,
        "query_vector_store",
        lambda **_: VectorSearchResult(filing_id="abc", chunks=[], related_filings=[]),
    )
    monkeypatch.setattr(rag, "run_rag_self_check", DummyTask())
    monkeypatch.setattr(rag, "snapshot_evidence_diff", DummyTask())
    monkeypatch.setattr(rag, "attach_diff_metadata", fake_diff_metadata)
    monkeypatch.setattr(rag, "_enqueue_evidence_snapshot", lambda *args, **kwargs: None)

    response = client.post(
        "/api/v1/rag/query",
        json={"question": "sample question", "filing_id": "abc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == ["no_context"]
    assert payload["context"] == []
    assert payload["answer"] == rag.NO_CONTEXT_ANSWER
    assert payload["rag_mode"] == "vector"
    assert payload["meta"]["evidence_diff"] == {"enabled": False, "removed": []}



def test_rag_query_intent_semipass(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "classify_query_intent",
        lambda question: {"decision": "semi_pass", "reason": "chit-chat", "model_used": "intent-test"},
    )

    def fail_query(**_kwargs):
        raise AssertionError("vector search should not be called")

    monkeypatch.setattr(vector_service, "query_vector_store", fail_query)
    monkeypatch.setattr(llm_service, "generate_rag_answer", fail_query)
    monkeypatch.setattr(rag, "run_rag_self_check", DummyTask())
    monkeypatch.setattr(rag, "snapshot_evidence_diff", DummyTask())
    monkeypatch.setattr(rag, "attach_diff_metadata", fake_diff_metadata)
    monkeypatch.setattr(rag, "_enqueue_evidence_snapshot", lambda *args, **kwargs: None)

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
        json={"question": "?? ????"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"] == ["intent_filter:semi_pass"]
    assert payload["answer"] == rag.INTENT_GENERAL_MESSAGE
    assert payload["rag_mode"] == "none"
    assert payload["meta"]["evidence_diff"] == {"enabled": False, "removed": []}


def test_rag_telemetry_records_events(monkeypatch):
    monkeypatch.setattr(rag.rag_metrics, "record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(rag, "audit_rag_event", lambda **kwargs: None)

    response = client.post(
        "/api/v1/rag/telemetry",
        json={
            "events": [
                {
                    "name": "rag.deeplink_opened",
                    "source": "chat",
                    "payload": {"documentId": "doc-1", "chunkId": "chunk-1"},
                }
            ]
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] == 1


def test_deeplink_resolve_route(monkeypatch):
    monkeypatch.setattr(rag.deeplink_service, "DEEPLINK_SECRET", "unit-test-secret", raising=False)
    monkeypatch.setattr(rag.deeplink_service, "DEEPLINK_TTL_SECONDS", 300, raising=False)
    monkeypatch.setattr(rag.deeplink_service, "DEEPLINK_VIEWER_BASE_URL", "/viewer", raising=False)

    token = rag.deeplink_service.issue_token(
        document_url="https://example.com/sample.pdf",
        page_number=2,
        char_start=5,
        char_end=15,
        sentence_hash="hash-xyz",
        chunk_id="chunk-xyz",
        document_id="filing-xyz",
        excerpt="Snippet",
    )

    response = client.get(f"/api/v1/rag/deeplink/{token}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page_number"] == 2
    assert payload["document_url"] == "https://example.com/sample.pdf"
    assert payload["chunk_id"] == "chunk-xyz"
    assert payload["excerpt"] == "Snippet"
