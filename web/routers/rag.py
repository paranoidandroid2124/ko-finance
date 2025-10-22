"""FastAPI routes for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import json
import uuid
from typing import Dict, Iterable, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.logging import get_logger
from llm import llm_service
from parse.tasks import run_rag_self_check
from schemas.api.rag import RAGQueryRequest, RAGQueryResponse
from services import vector_service

logger = get_logger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


def _vector_search(question: str, filing_id: str, top_k: int) -> List[Dict[str, object]]:
    try:
        return vector_service.query_vector_store(
            query_text=question,
            filing_id=filing_id,
            top_k=top_k,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Vector search failed for filing %s: %s", filing_id, exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Vector search is currently unavailable.")


def _no_context_response(question: str, filing_id: str, trace_id: str) -> RAGQueryResponse:
    return RAGQueryResponse(
        question=question,
        filing_id=filing_id,
        answer="관련 근거 문서를 찾지 못했습니다. 다른 질문을 시도해 주세요.",
        context=[],
        citations={},
        warnings=["no_context"],
        highlights=[],
        error=None,
        original_answer=None,
        model_used=None,
        trace_id=trace_id,
    )


def _stream_no_context_event(question: str, filing_id: str, trace_id: str) -> bytes:
    event = {
        "type": "final",
        "payload": {
            "question": question,
            "filing_id": filing_id,
            "trace_id": trace_id,
            "answer": "관련 근거 문서를 찾지 못했습니다. 다른 질문을 시도해 주세요.",
            "context": [],
            "citations": {},
            "warnings": ["no_context"],
            "highlights": [],
            "error": None,
            "original_answer": None,
            "model_used": None,
        },
    }
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(request: RAGQueryRequest) -> RAGQueryResponse:
    """Return a RAG answer for a filing-specific question."""
    question = request.question.strip()
    filing_id = request.filing_id.strip()
    trace_id = str(uuid.uuid4())

    context_chunks = _vector_search(question, filing_id, request.top_k)

    if not context_chunks:
        logger.info("No context chunks found for filing %s (trace_id=%s).", filing_id, trace_id)
        return _no_context_response(question, filing_id, trace_id)

    result = llm_service.answer_with_rag(question, context_chunks)
    error = result.get("error")
    if error and not (
        str(error).startswith("missing_citations") or str(error).startswith("guardrail_violation")
    ):
        logger.error("LLM response error for filing %s: %s", filing_id, error)
        raise HTTPException(status_code=500, detail=f"LLM answer failed: {error}")

    context: List[Dict[str, object]] = list(result.get("context") or context_chunks)
    citations: Dict[str, List[str]] = dict(result.get("citations") or {})
    warnings: List[str] = list(result.get("warnings") or [])
    highlights: List[Dict[str, object]] = list(result.get("highlights") or [])

    response = RAGQueryResponse(
        question=question,
        filing_id=filing_id,
        answer=result.get("answer", "답변을 생성하지 못했습니다."),
        context=context,
        citations=citations,
        warnings=warnings,
        highlights=highlights,
        error=error,
        original_answer=result.get("original_answer"),
        model_used=result.get("model_used"),
        trace_id=trace_id,
    )

    if request.run_self_check:
        payload = {
            "question": question,
            "filing_id": filing_id,
            "answer": response.model_dump(),
            "context": context_chunks,
            "trace_id": trace_id,
        }
        try:
            run_rag_self_check.delay(payload)
        except Exception as exc:  # pragma: no cover - background task failure
            logger.warning(
                "Failed to enqueue RAG self-check (trace_id=%s): %s", trace_id, exc, exc_info=True
            )

    return response


@router.post("/query/stream")
def query_rag_stream(request: RAGQueryRequest):
    """Stream a RAG answer token-by-token."""
    question = request.question.strip()
    filing_id = request.filing_id.strip()
    trace_id = str(uuid.uuid4())

    context_chunks = _vector_search(question, filing_id, request.top_k)

    if not context_chunks:
        logger.info("No context chunks found for filing %s (trace_id=%s).", filing_id, trace_id)

        def empty_stream() -> Iterable[bytes]:
            yield _stream_no_context_event(question, filing_id, trace_id)

        return StreamingResponse(empty_stream(), media_type="application/x-ndjson")

    def event_stream() -> Iterable[bytes]:
        try:
            for event in llm_service.stream_answer_with_rag(question, context_chunks):
                if event.get("type") == "final":
                    payload = event.get("payload", {})
                    payload["question"] = question
                    payload["filing_id"] = filing_id
                    payload["trace_id"] = trace_id
                    event["payload"] = payload

                    if request.run_self_check:
                        try:
                            run_rag_self_check.delay(
                                {
                                    "question": question,
                                    "filing_id": filing_id,
                                    "answer": payload,
                                    "context": context_chunks,
                                    "trace_id": trace_id,
                                }
                            )
                        except Exception as exc:  # pragma: no cover - background task failure
                            logger.warning(
                                "Failed to enqueue RAG self-check (trace_id=%s): %s", trace_id, exc, exc_info=True
                            )

                yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        except Exception as exc:
            logger.error("Streaming RAG response failed for filing %s: %s", filing_id, exc, exc_info=True)
            error_event = {"type": "error", "message": "Streaming RAG response failed."}
            yield (json.dumps(error_event, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


__all__ = ["router"]
