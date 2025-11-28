"""Hybrid BM25 + vector retrieval with optional Vertex AI reranking."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.env import env_int, env_str
from services import vector_service

logger = logging.getLogger(__name__)

SEARCH_MODE = (env_str("SEARCH_MODE", "hybrid") or "vector").strip().lower()
BM25_TOPN = env_int("BM25_TOPN", 80, minimum=1)
DENSE_TOPN = env_int("DENSE_TOPN", 80, minimum=1)
RRF_K = env_int("RRF_K", 60, minimum=1)
RERANK_PROVIDER = (env_str("RERANK_PROVIDER", "vertex") or "").strip().lower()
RERANK_MODEL = (env_str("RERANK_MODEL", "semantic-ranker-default@latest") or "").strip()
RERANK_CONFIG = (env_str("RERANK_RANKING_CONFIG", "") or "").strip()
RERANK_TOPK = env_int("RERANK_TOPK", 50, minimum=1)
RERANK_TIMEOUT_MS = env_int("RERANK_TIMEOUT_MS", 2000, minimum=500)
RERANK_CACHE_TTL = env_int("RERANK_CACHE_TTL_S", 7 * 24 * 3600, minimum=60)

_BM25_AVAILABLE = True


@dataclass
class CandidateAccumulator:
    """Track per-document ranking signals for fusion."""

    document_id: str
    doc_type: str = "filing"
    title: Optional[str] = None
    published_at: Optional[str] = None
    dense_rank: Optional[int] = None
    dense_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    fused_score: float = 0.0

    def to_related_dict(self) -> Dict[str, Any]:
        payload = {
            "filing_id": self.document_id,
            "score": float(self.fused_score),
            "title": self.title,
            "published_at": self.published_at,
            "sentiment": None,
            "doc_type": self.doc_type,
            "dense_rank": self.dense_rank,
            "bm25_rank": self.bm25_rank,
        }
        return payload


@dataclass
class DocumentProfile:
    """Content used for reranking/caching."""

    document_id: str
    doc_type: str
    title: str
    content: str


class VertexReranker:
    """Minimal Vertex AI Ranking API client with local TTL cache."""

    _SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)

    def __init__(
        self,
        *,
        ranking_config: str,
        model: str,
        top_n: int,
        timeout_ms: int,
        cache_ttl: int,
    ) -> None:
        self._ranking_config = ranking_config
        self._model = model
        self._top_n = top_n
        self._timeout = timeout_ms / 1000.0
        self._cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._session = None
        self._available = bool(ranking_config and model)
        self._enabled = self._available
        self._cache_hits = 0

    def enabled(self) -> bool:
        return self._enabled

    def stats(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "model": self._model,
        }

    def rerank(
        self,
        query: str,
        records: Sequence[DocumentProfile],
    ) -> Optional[List[Dict[str, Any]]]:
        if not self._enabled or not records:
            return None
        if len(records) == 1:
            return [{"id": records[0].document_id, "score": 1.0}]

        try:
            request_records = [
                {
                    "id": profile.document_id,
                    "content": profile.content,
                    "title": profile.title,
                }
                for profile in records[: self._top_n]
            ]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to build rerank payload: %s", exc)
            return None

        cache_key = self._cache_key(query, request_records)
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] <= self._cache_ttl:
            self._cache_hits += 1
            return cached[1]

        session = self._ensure_session()
        if session is None:
            return None

        payload = {
            "rankingConfig": self._ranking_config,
            "model": self._model,
            "topN": min(self._top_n, len(request_records)),
            "query": query,
            "records": request_records,
        }

        url = (
            f"https://discoveryengine.googleapis.com/v1alpha/{self._ranking_config}:rank"
        )
        try:
            response = session.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # pragma: no cover - external service
            logger.warning("Vertex rerank request failed: %s", exc, exc_info=True)
            return None

        ranked_records: List[Dict[str, Any]] = []
        for entry in data.get("records") or data.get("rankedRecords") or []:
            doc_id = entry.get("id")
            score = entry.get("score")
            if not doc_id:
                continue
            ranked_records.append({"id": doc_id, "score": float(score or 0.0)})

        if not ranked_records:
            return None

        self._cache[cache_key] = (now, ranked_records)
        return ranked_records

    def _ensure_session(self):
        if self._session is not None:
            return self._session
        try:  # pragma: no cover - requires google-auth at runtime
            from google.auth import default
            from google.auth.transport.requests import AuthorizedSession
        except ImportError:
            logger.warning("google-auth is not available; disabling Vertex reranker.")
            self._enabled = False
            return None
        try:
            credentials, _ = default(scopes=self._SCOPES)
        except Exception as exc:
            logger.warning("Unable to load Google credentials: %s", exc)
            self._enabled = False
            return None
        self._session = AuthorizedSession(credentials)
        return self._session

    def _cache_key(self, query: str, records: Sequence[Dict[str, Any]]) -> str:
        digest = hashlib.sha1()
        digest.update(query.strip().encode("utf-8"))
        for record in records:
            digest.update(record.get("id", "").encode("utf-8"))
            digest.update(
                hashlib.sha1(
                    (record.get("content") or "").encode("utf-8"),
                ).digest()
            )
        return digest.hexdigest()


_RERANKER: Optional[VertexReranker] = None
if RERANK_PROVIDER == "vertex" and RERANK_CONFIG and RERANK_MODEL:
    _RERANKER = VertexReranker(
        ranking_config=RERANK_CONFIG,
        model=RERANK_MODEL,
        top_n=RERANK_TOPK,
        timeout_ms=RERANK_TIMEOUT_MS,
        cache_ttl=RERANK_CACHE_TTL,
    )


def is_hybrid_enabled() -> bool:
    return SEARCH_MODE == "hybrid"


def query_hybrid(
    db: Session,
    question: str,
    *,
    filing_id: Optional[str],
    top_k: int,
    max_filings: int,
    filters: Dict[str, Any],
    use_reranker: Optional[bool] = None,
    multi_mode: bool = False,
) -> vector_service.VectorSearchResult:
    """Execute BM25 + dense retrieval with optional reranking."""

    dense_cap = max(DENSE_TOPN, max_filings)
    base_result = vector_service.query_vector_store(
        query_text=question,
        filing_id=filing_id,
        top_k=top_k,
        max_filings=dense_cap,
        filters=filters,
        multi_mode=multi_mode,
    )
    dense_candidates = _extract_dense_candidates(base_result.related_filings)
    bm25_candidates = _fetch_bm25_candidates(db, question, filters, limit=BM25_TOPN)
    if not dense_candidates and not bm25_candidates:
        return base_result

    fused_candidates = _reciprocal_rank_fusion(
        dense_candidates,
        bm25_candidates,
        max_candidates=max(dense_cap, BM25_TOPN),
    )

    if filing_id:
        _ensure_seed_candidate(fused_candidates, filing_id)

    reranked = fused_candidates
    rerank_allowed = use_reranker if use_reranker is not None else True
    if (
        rerank_allowed
        and _RERANKER
        and _RERANKER.enabled()
        and fused_candidates
    ):
        rerank_records = _build_rerank_profiles(
            db,
            fused_candidates[: RERANK_TOPK],
        )
        ranked = _RERANKER.rerank(question, rerank_records)
        if ranked:
            reranked = _apply_rerank_scores(fused_candidates, ranked)

    final_candidates = reranked[:max_filings] if reranked else fused_candidates[:max_filings]
    selected = filing_id or _select_document_id(final_candidates, base_result, filters)

    if selected and selected == base_result.filing_id:
        final_result = base_result
    else:
        final_result = vector_service.query_vector_store(
            query_text=question,
            filing_id=selected,
            top_k=top_k,
            max_filings=max_filings,
            filters=filters,
            multi_mode=multi_mode,
        )

    final_result.related_filings = [entry.to_related_dict() for entry in final_candidates]
    return final_result


def run_bm25_ranking(
    db: Session,
    question: str,
    *,
    filters: Dict[str, Any],
    limit: int,
) -> vector_service.VectorSearchResult:
    """Expose BM25-only ranking for evaluation scripts."""

    candidates = _fetch_bm25_candidates(db, question, filters, limit=limit)
    for candidate in candidates:
        candidate.fused_score = float(candidate.bm25_score or 0.0)
    related = [entry.to_related_dict() for entry in candidates[:limit]]
    selected = related[0]["filing_id"] if related else None
    return vector_service.VectorSearchResult(
        filing_id=selected,
        chunks=[],
        related_filings=related,
    )


def _select_document_id(
    candidates: Sequence[CandidateAccumulator],
    base_result: vector_service.VectorSearchResult,
    filters: Dict[str, Any],
) -> Optional[str]:
    if candidates:
        return candidates[0].document_id
    return base_result.filing_id


def _ensure_seed_candidate(
    candidates: List[CandidateAccumulator],
    document_id: str,
) -> None:
    if any(item.document_id == document_id for item in candidates):
        return
    candidates.insert(
        0,
        CandidateAccumulator(
            document_id=document_id,
            doc_type="filing",
            title=None,
            published_at=None,
            fused_score=1.0,
        ),
    )


def _extract_dense_candidates(
    related_filings: Sequence[Mapping[str, Any]],
) -> List[CandidateAccumulator]:
    candidates: List[CandidateAccumulator] = []
    for idx, entry in enumerate(related_filings or [], start=1):
        doc_id = entry.get("filing_id")
        if not doc_id:
            continue
        candidate = CandidateAccumulator(
            document_id=str(doc_id),
            doc_type=str(entry.get("doc_type") or "filing"),
            title=entry.get("title"),
            published_at=entry.get("published_at"),
            dense_rank=idx,
            dense_score=float(entry.get("score") or 0.0),
            fused_score=0.0,
        )
        candidates.append(candidate)
    return candidates


def _fetch_bm25_candidates(
    db: Session,
    question: str,
    filters: Dict[str, Any],
    *,
    limit: int,
) -> List[CandidateAccumulator]:
    global _BM25_AVAILABLE
    if not _BM25_AVAILABLE:
        return []

    params = _build_bm25_params(question, filters, limit)
    try:
        filings = db.execute(_FILINGS_QUERY, params).fetchall()
        news = db.execute(_NEWS_QUERY, params).fetchall()
    except SQLAlchemyError as exc:
        logger.warning("BM25 query failed; disabling hybrid BM25 stage: %s", exc)
        _BM25_AVAILABLE = False
        return []

    candidates: List[CandidateAccumulator] = []
    for idx, row in enumerate(filings, start=1):
        candidates.append(
            CandidateAccumulator(
                document_id=str(row.document_id),
                doc_type="filing",
                title=row.title,
                published_at=_format_timestamp(row.published_at),
                bm25_rank=idx,
                bm25_score=float(row.bm25_score or 0.0),
            )
        )
    filing_count = len(candidates)
    for offset, row in enumerate(news, start=1):
        candidates.append(
            CandidateAccumulator(
                document_id=str(row.document_id),
                doc_type="news",
                title=row.title,
                published_at=_format_timestamp(row.published_at),
                bm25_rank=filing_count + offset,
                bm25_score=float(row.bm25_score or 0.0),
            )
        )
    return candidates


def _reciprocal_rank_fusion(
    dense: Sequence[CandidateAccumulator],
    sparse: Sequence[CandidateAccumulator],
    *,
    max_candidates: int,
) -> List[CandidateAccumulator]:
    combined: Dict[str, CandidateAccumulator] = {}

    def _accumulate(source: Sequence[CandidateAccumulator], kind: str) -> None:
        for idx, candidate in enumerate(source, start=1):
            entry = combined.setdefault(
                candidate.document_id,
                CandidateAccumulator(
                    document_id=candidate.document_id,
                    doc_type=candidate.doc_type,
                    title=candidate.title,
                    published_at=candidate.published_at,
                ),
            )
            entry.title = entry.title or candidate.title
            entry.doc_type = entry.doc_type or candidate.doc_type
            entry.published_at = entry.published_at or candidate.published_at
            if kind == "dense":
                entry.dense_rank = candidate.dense_rank or idx
                entry.dense_score = candidate.dense_score
            else:
                entry.bm25_rank = candidate.bm25_rank or idx
                entry.bm25_score = candidate.bm25_score
            entry.fused_score += 1.0 / (RRF_K + idx)

    _accumulate(dense, "dense")
    _accumulate(sparse, "bm25")

    ranked = sorted(
        combined.values(),
        key=lambda item: item.fused_score,
        reverse=True,
    )
    return ranked[:max_candidates]


def _build_rerank_profiles(
    db: Session,
    candidates: Sequence[CandidateAccumulator],
) -> List[DocumentProfile]:
    doc_ids = [candidate.document_id for candidate in candidates]
    profiles = _load_document_profiles(db, doc_ids)
    records: List[DocumentProfile] = []
    for candidate in candidates:
        profile = profiles.get(candidate.document_id)
        if not profile:
            continue
        records.append(profile)
    return records


def _load_document_profiles(
    db: Session,
    document_ids: Sequence[str],
) -> Dict[str, DocumentProfile]:
    from models.filing import Filing  # local import to avoid circular
    from models.news import NewsSignal

    parsed_ids: List[uuid.UUID] = []
    id_map: Dict[uuid.UUID, str] = {}
    for doc_id in document_ids:
        try:
            parsed = uuid.UUID(doc_id)
        except (ValueError, TypeError):
            continue
        parsed_ids.append(parsed)
        id_map[parsed] = doc_id

    profiles: Dict[str, DocumentProfile] = {}
    if not parsed_ids:
        return profiles

    filing_rows = (
        db.query(Filing)
        .filter(Filing.id.in_(parsed_ids))
        .all()
    )
    for row in filing_rows:
        doc_id = id_map.get(row.id)
        if not doc_id:
            continue
        title = row.report_name or row.title or row.corp_name or "Filing"
        content = (row.raw_md or "")[:4000]
        profiles[doc_id] = DocumentProfile(
            document_id=doc_id,
            doc_type="filing",
            title=title,
            content=content,
        )

    news_rows = (
        db.query(NewsSignal)
        .filter(NewsSignal.id.in_(parsed_ids))
        .all()
    )
    for row in news_rows:
        doc_id = id_map.get(row.id)
        if not doc_id:
            continue
        title = row.headline or "News"
        summary = row.summary or ""
        content = f"{title}\n\n{summary}"[:2000]
        profiles[doc_id] = DocumentProfile(
            document_id=doc_id,
            doc_type="news",
            title=title,
            content=content,
        )

    return profiles


def _apply_rerank_scores(
    candidates: Sequence[CandidateAccumulator],
    ranking: Sequence[Mapping[str, Any]],
) -> List[CandidateAccumulator]:
    scores = {entry.get("id"): float(entry.get("score") or 0.0) for entry in ranking if entry.get("id")}
    if not scores:
        return list(candidates)
    ranked: List[CandidateAccumulator] = []
    id_map = {candidate.document_id: candidate for candidate in candidates}
    seen: set[str] = set()
    for doc_id, score in scores.items():
        candidate = id_map.get(doc_id)
        if not candidate:
            continue
        clone = CandidateAccumulator(
            document_id=candidate.document_id,
            doc_type=candidate.doc_type,
            title=candidate.title,
            published_at=candidate.published_at,
            dense_rank=candidate.dense_rank,
            dense_score=candidate.dense_score,
            bm25_rank=candidate.bm25_rank,
            bm25_score=candidate.bm25_score,
            fused_score=score,
        )
        ranked.append(clone)
        seen.add(doc_id)
    for candidate in candidates:
        if candidate.document_id in seen:
            continue
        ranked.append(candidate)
    return ranked


def _format_timestamp(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _build_bm25_params(
    question: str,
    filters: Dict[str, Any],
    limit: int,
) -> Dict[str, Any]:
    min_ts = filters.get("min_published_at_ts")
    max_ts = filters.get("max_published_at_ts")
    min_dt = datetime.fromtimestamp(min_ts, tz=timezone.utc) if isinstance(min_ts, (int, float)) else None
    max_dt = datetime.fromtimestamp(max_ts, tz=timezone.utc) if isinstance(max_ts, (int, float)) else None
    return {
        "raw_query": question,
        "ts_query": question,
        "limit": limit,
        "ticker": filters.get("ticker"),
        "min_published_at": min_dt,
        "max_published_at": max_dt,
    }


_FILINGS_QUERY = text(
    """
    WITH q AS (
        SELECT
            plainto_tsquery('simple', :ts_query) AS tsq,
            :raw_query AS raw
    )
    SELECT
        f.id::text AS document_id,
        COALESCE(f.report_name, f.title, f.corp_name, 'Filing') AS title,
        f.filed_at AS published_at,
        (
            0.7 * ts_rank_cd(f.search_tsv, q.tsq) +
            0.3 * similarity(f.title, q.raw)
        ) AS bm25_score
    FROM filings f
    CROSS JOIN q
    WHERE
        (f.search_tsv @@ q.tsq OR f.title % q.raw)
        AND (:ticker IS NULL OR lower(f.ticker) = lower(:ticker))
        AND (:min_published_at IS NULL OR f.filed_at >= :min_published_at)
        AND (:max_published_at IS NULL OR f.filed_at <= :max_published_at)
    ORDER BY bm25_score DESC NULLS LAST
    LIMIT :limit
    """
)

_NEWS_QUERY = text(
    """
    WITH q AS (
        SELECT
            plainto_tsquery('simple', :ts_query) AS tsq,
            :raw_query AS raw
    )
    SELECT
        n.id::text AS document_id,
        COALESCE(n.headline, 'News') AS title,
        n.published_at AS published_at,
        (
            0.7 * ts_rank_cd(n.search_tsv, q.tsq) +
            0.3 * similarity(n.headline, q.raw)
        ) AS bm25_score
    FROM news_signals n
    CROSS JOIN q
    WHERE
        (n.search_tsv @@ q.tsq OR n.headline % q.raw)
        AND (:ticker IS NULL OR lower(n.ticker) = lower(:ticker))
        AND (:min_published_at IS NULL OR n.published_at >= :min_published_at)
        AND (:max_published_at IS NULL OR n.published_at <= :max_published_at)
    ORDER BY bm25_score DESC NULLS LAST
    LIMIT :limit
    """
)


__all__ = [
    "is_hybrid_enabled",
    "query_hybrid",
    "run_bm25_ranking",
]
