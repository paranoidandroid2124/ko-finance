"""FastAPI routes for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from core.logging import get_logger
from llm import llm_service
from parse.tasks import run_rag_self_check
from schemas.api.rag import RAGQueryRequest, RAGQueryResponse
from services import vector_service

logger = get_logger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(request: RAGQueryRequest) -> RAGQueryResponse:
    """Return a RAG answer for a filing-specific question."""
    question = request.question.strip()
    filing_id = request.filing_id.strip()
    trace_id = str(uuid.uuid4())

    try:
        context_chunks = vector_service.query_vector_store(
            query_text=question,
            filing_id=filing_id,
            top_k=request.top_k,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Vector search failed for filing %s: %s", filing_id, exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Vector search is currently unavailable.")

    if not context_chunks:
        logger.info("No context chunks found for filing %s (trace_id=%s).", filing_id, trace_id)
        return RAGQueryResponse(
            question=question,
            filing_id=filing_id,
            answer="관련 문서를 찾지 못했습니다. 질문을 구체화해주세요.",
            context=[],
            citations={},
            warnings=["no_context"],
            highlights=[],
            error=None,
            original_answer=None,
            model_used=None,
            trace_id=trace_id,
        )

    result = llm_service.answer_with_rag(question, context_chunks)
    error = result.get("error")
    if error and not (
        str(error).startswith("missing_citations") or str(error).startswith("guardrail_violation")
    ):
        logger.error("LLM response error for filing %s: %s", filing_id, error)
        raise HTTPException(status_code=500, detail=f"LLM answer failed: {error}")

    # Ensure serialisable collections.
    context: List[Dict[str, object]] = list(result.get("context") or context_chunks)
    citations: Dict[str, List[str]] = dict(result.get("citations") or {})
    warnings: List[str] = list(result.get("warnings") or [])
    highlights: List[Dict[str, object]] = list(result.get("highlights") or [])

    response = RAGQueryResponse(
        question=question,
        filing_id=filing_id,
        answer=result.get("answer", "응답이 생성되지 않았습니다."),
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
            logger.warning("Failed to enqueue RAG self-check (trace_id=%s): %s", trace_id, exc, exc_info=True)

    return response


__all__ = ["router"]


