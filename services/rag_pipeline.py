"""Hybrid RAG pipeline orchestration (BM25 + embeddings + rerank)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy.orm import Session

from core.logging import get_logger
from schemas.api.rag import (
    EvidenceSchema,
    RagGridRequest,
    RagQueryFiltersSchema,
    RagQueryRequest,
    RagWarningSchema,
)
from services import hybrid_search, vector_service
from services.rag_shared import safe_float

logger = get_logger(__name__)

DEFAULT_SOURCE_WEIGHTS: Dict[str, float] = {
    "filing": 1.2,
    "event": 1.1,
    "news": 1.0,
    "sector": 0.9,
    "portfolio": 0.9,
    "memo": 0.8,
}


@dataclass(slots=True)
class RagPipelineResult:
    """Structured output for downstream answer generation."""

    evidence: List[EvidenceSchema]
    raw_chunks: List[Dict[str, Any]]
    related_documents: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[RagWarningSchema] = field(default_factory=list)
    timings_ms: Dict[str, int] = field(default_factory=dict)
    trace: Dict[str, Any] = field(default_factory=dict)


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _filters_to_vector_payload(filters: RagQueryFiltersSchema, primary_ticker: Optional[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if primary_ticker:
        payload["ticker"] = primary_ticker

    min_dt = _parse_iso_timestamp(filters.dateGte)
    max_dt = _parse_iso_timestamp(filters.dateLte)
    if min_dt:
        payload["min_published_at_ts"] = min_dt.timestamp()
    if max_dt:
        payload["max_published_at_ts"] = max_dt.timestamp()

    if filters.sectors:
        payload["sector"] = filters.sectors[0]
    if filters.eventTags:
        payload["event_tag"] = filters.eventTags[0]
    return payload


def _weight_for_source(source_type: Optional[str]) -> float:
    if not source_type:
        return 1.0
    return DEFAULT_SOURCE_WEIGHTS.get(source_type, 1.0)


def _normalize_chunk_to_evidence(
    chunk: Mapping[str, Any],
    *,
    source_types: Sequence[str],
    fallback_source_type: str = "filing",
) -> Optional[EvidenceSchema]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    source_type = (
        metadata.get("source_type")
        or chunk.get("source_type")
        or chunk.get("doc_type")
        or fallback_source_type
    )
    if source_types and source_type not in set(source_types):
        return None

    def _list(value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        result: List[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    anchor = chunk.get("anchor")
    anchors = []
    if isinstance(anchor, dict):
        paragraph = anchor.get("paragraph_id")
        if paragraph:
            anchors.append(str(paragraph))
        anchor_id = anchor.get("id")
        if anchor_id:
            anchors.append(str(anchor_id))
    elif anchor:
        anchors = _list(anchor)

    diff_payload = metadata.get("diff") if isinstance(metadata.get("diff"), dict) else None
    self_check_payload = metadata.get("self_check") if isinstance(metadata.get("self_check"), dict) else None

    score = safe_float(chunk.get("score"))
    rerank_score = safe_float(chunk.get("rerank_score"))
    weight = _weight_for_source(source_type)
    confidence = safe_float(metadata.get("confidence"))
    summary = metadata.get("summary") or chunk.get("summary")

    payload = {
        "sourceType": source_type,
        "sourceId": chunk.get("filing_id") or metadata.get("source_id") or chunk.get("id"),
        "sourceSlug": metadata.get("slug"),
        "title": chunk.get("title") or metadata.get("title"),
        "publisher": metadata.get("publisher") or chunk.get("corp_name"),
        "ticker": metadata.get("ticker") or chunk.get("ticker"),
        "sector": metadata.get("sector") or chunk.get("sector"),
        "sentiments": _list(metadata.get("sentiments")),
        "publishedAt": chunk.get("filed_at") or metadata.get("published_at"),
        "section": chunk.get("section"),
        "pageNumber": chunk.get("page_number"),
        "anchors": anchors,
        "content": chunk.get("quote") or chunk.get("content") or "",
        "summary": summary,
        "score": score * weight if score is not None else None,
        "rerankScore": rerank_score,
        "confidence": confidence,
        "diff": diff_payload,
        "selfCheck": self_check_payload,
        "metadata": {
            "chunkId": chunk.get("chunk_id") or chunk.get("id"),
            "anchor": anchor,
            "weight": weight,
        },
        "viewerUrl": metadata.get("viewer_url") or chunk.get("viewer_url"),
        "downloadUrl": metadata.get("download_url") or chunk.get("download_url"),
    }

    if not payload["content"]:
        return None

    try:
        return EvidenceSchema(**payload)
    except Exception as exc:
        logger.debug("Dropping chunk due to validation error: %s", exc)
        return None


def _gather_chunks_for_documents(
    *,
    question: str,
    seed_result: vector_service.VectorSearchResult,
    max_chunks: int,
    filters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = list(seed_result.chunks or [])
    if len(chunks) >= max_chunks:
        return chunks

    seen: set[str] = set()
    if seed_result.filing_id:
        seen.add(str(seed_result.filing_id))

    for related in seed_result.related_filings:
        doc_id = str(related.get("filing_id") or "")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        try:
            follow_up = vector_service.query_vector_store(
                query_text=question,
                filing_id=doc_id,
                top_k=max(2, max_chunks // 2),
                max_filings=1,
                filters=filters,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Vector follow-up failed for doc=%s: %s", doc_id, exc)
            continue
        chunks.extend(follow_up.chunks or [])
        if len(chunks) >= max_chunks:
            break
    return chunks


def run_rag_query(
    db: Session,
    request: RagQueryRequest,
    *,
    use_reranker: Optional[bool] = None,
) -> RagPipelineResult:
    """Execute the retrieval phase and return normalized evidence."""

    start = time.perf_counter()
    primary_ticker = next((ticker for ticker in request.tickers if ticker), None)
    if request.filters.tickers and not primary_ticker:
        primary_ticker = next((ticker for ticker in request.filters.tickers if ticker), None)

    vector_filters = _filters_to_vector_payload(request.filters, primary_ticker)

    top_k = request.topK
    max_filings = request.maxFilings or max(5, top_k)
    try:
        base_result = hybrid_search.query_hybrid(
            db,
            request.query,
            filing_id=request.filingId,
            top_k=top_k,
            max_filings=max_filings,
            filters=vector_filters,
            use_reranker=use_reranker,
        )
    except Exception as exc:
        logger.error("Hybrid retrieval failed: %s", exc, exc_info=True)
        raise RuntimeError("retrieval_failed") from exc

    retrieval_ms = int((time.perf_counter() - start) * 1000)
    chunk_budget = max(top_k * 2, 6)
    chunks = _gather_chunks_for_documents(
        question=request.query,
        seed_result=base_result,
        max_chunks=chunk_budget,
        filters=vector_filters,
    )
    raw_chunks: List[Dict[str, Any]] = [dict(chunk) for chunk in chunks]

    evidence: List[EvidenceSchema] = []
    allowed_sources = request.sourceTypes or ["filing", "news", "event"]

    for chunk in chunks:
        normalized = _normalize_chunk_to_evidence(
            chunk,
            source_types=allowed_sources,
        )
        if not normalized:
            continue
        evidence.append(normalized)
        if len(evidence) >= top_k:
            break

    warnings: List[RagWarningSchema] = []
    if not evidence:
        warnings.append(RagWarningSchema(code="rag.no_evidence", message="검색된 증거가 없습니다. 질문을 다시 작성해 주세요."))

    total_ms = int((time.perf_counter() - start) * 1000)
    timings = {"retrievalMs": retrieval_ms, "totalMs": total_ms}

    return RagPipelineResult(
        evidence=evidence,
        raw_chunks=raw_chunks,
        related_documents=list(base_result.related_filings),
        warnings=warnings,
        timings_ms=timings,
        trace={
            "filters": vector_filters,
            "relatedCount": len(base_result.related_filings),
            "selectedFilingId": base_result.filing_id,
        },
    )


def estimate_grid_work_units(request: RagGridRequest) -> int:
    """Estimate worker units needed for QA grid fan-out."""

    cell_count = len(request.tickers) * len(request.questions)
    return max(cell_count, 1)


__all__ = [
    "DEFAULT_SOURCE_WEIGHTS",
    "RagPipelineResult",
    "estimate_grid_work_units",
    "run_rag_query",
]
