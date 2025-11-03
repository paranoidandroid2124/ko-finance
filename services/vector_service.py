"""Interface to Qdrant vector store used by the RAG pipeline."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import litellm
from litellm.exceptions import ContextWindowExceededError
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from services.rag_shared import build_anchor_payload, normalize_reliability

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_CONNECT_RETRIES = int(os.getenv("QDRANT_CONNECT_RETRIES", "3"))
QDRANT_RETRY_DELAY_SEC = float(os.getenv("QDRANT_RETRY_DELAY_SEC", "1.5"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BATCH_SIZE = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")))
EMBEDDING_MAX_CONTENT_CHARS = max(1024, int(os.getenv("EMBEDDING_MAX_CONTENT_CHARS", "12000")))
VECTOR_DIMENSION = 1536
COLLECTION_NAME = "k-finance-rag-collection"

_qdrant_client: Optional[QdrantClient] = None


@dataclass
class VectorSearchResult:
    filing_id: Optional[str]
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    related_filings: List[Dict[str, Any]] = field(default_factory=list)


def _normalize_chunk_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(raw_payload)
    metadata = payload.pop("metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    chunk_id = payload.get("chunk_id") or payload.get("id") or metadata.get("chunk_id")
    if chunk_id:
        payload["chunk_id"] = str(chunk_id)
        payload.setdefault("id", payload["chunk_id"])

    quote = metadata.get("quote") or payload.get("quote")
    if not quote:
        quote = metadata.get("content") or payload.get("content") or ""
    payload["quote"] = quote

    for key in ("section", "page_number", "source_reliability", "created_at"):
        if payload.get(key) is None and metadata.get(key) is not None:
            payload[key] = metadata[key]

    anchor = build_anchor_payload(payload, metadata)
    if anchor:
        payload["anchor"] = anchor

    reliability = normalize_reliability(payload.get("source_reliability"))
    if reliability:
        payload["source_reliability"] = reliability

    if metadata:
        payload["metadata"] = metadata

    return payload


def _create_client() -> QdrantClient:
    last_error: Optional[Exception] = None
    for attempt in range(1, QDRANT_CONNECT_RETRIES + 1):
        try:
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            logger.info("Connected to Qdrant at %s:%s (attempt %d).", QDRANT_HOST, QDRANT_PORT, attempt)
            return client
        except Exception as exc:
            last_error = exc
            logger.warning("Qdrant connection attempt %d failed: %s", attempt, exc, exc_info=True)
            if attempt < QDRANT_CONNECT_RETRIES:
                time.sleep(QDRANT_RETRY_DELAY_SEC)
    raise ConnectionError(f"Unable to connect to Qdrant: {last_error}")


def _client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = _create_client()
    return _qdrant_client


def init_collection() -> None:
    client = _client()
    try:
        client.get_collection(collection_name=COLLECTION_NAME)
        logger.debug("Qdrant collection '%s' already exists.", COLLECTION_NAME)
    except Exception:
        logger.info("Creating Qdrant collection '%s'.", COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE),
        )


def store_chunk_vectors(
    filing_id: str,
    chunks: List[Dict[str, Any]],
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not chunks:
        logger.warning("No chunks provided for filing %s. Skipping vector store upsert.", filing_id)
        return

    client = _client()
    init_collection()

    contents: List[str] = []
    for chunk in chunks:
        raw_content = chunk.get("content", "")
        text = raw_content if isinstance(raw_content, str) else str(raw_content)
        if len(text) > EMBEDDING_MAX_CONTENT_CHARS:
            logger.debug(
                "Truncating chunk content for filing %s (chars=%d -> %d).",
                filing_id,
                len(text),
                EMBEDDING_MAX_CONTENT_CHARS,
            )
            text = text[:EMBEDDING_MAX_CONTENT_CHARS]
        contents.append(text)

    if not any(contents):
        logger.warning("All chunk contents are empty for filing %s.", filing_id)
        return

    vectors: List[List[float]] = []
    index = 0
    batch_size = EMBEDDING_BATCH_SIZE
    total = len(contents)
    while index < total:
        end = min(total, index + batch_size)
        batch = contents[index:end]
        try:
            embedding_response = litellm.embedding(model=EMBEDDING_MODEL, input=batch)
        except ContextWindowExceededError as exc:
            if len(batch) == 1:
                original_text = contents[index]
                if len(original_text) > 1024:
                    new_length = max(1024, len(original_text) // 2)
                    clipped = original_text[:new_length]
                    logger.warning(
                        "Embedding chunk exceeded context limit for filing %s (chars=%d). "
                        "Retrying with truncated content (%d chars).",
                        filing_id,
                        len(original_text),
                        len(clipped),
                    )
                    contents[index] = clipped
                    continue
                logger.error(
                    "Embedding chunk still exceeds context limit for filing %s after truncation.",
                    filing_id,
                    exc_info=True,
                )
                raise
            prev_batch = batch_size
            batch_size = max(1, batch_size // 2)
            logger.debug(
                "Reducing embedding batch size for filing %s: %d -> %d items (context limit hit).",
                filing_id,
                prev_batch,
                batch_size,
            )
            continue
        except Exception as exc:
            logger.error("Embedding generation failed for filing %s: %s", filing_id, exc, exc_info=True)
            raise

        vectors.extend(item["embedding"] for item in embedding_response.data)
        index = end
        batch_size = EMBEDDING_BATCH_SIZE
    points: List[models.PointStruct] = []
    for idx, chunk in enumerate(chunks):
        payload = {
            "filing_id": filing_id,
            "id": chunk.get("id"),
            "chunk_id": chunk.get("id"),
            "page_number": chunk.get("page_number"),
            "type": chunk.get("type"),
            "section": chunk.get("section"),
            "source": chunk.get("source"),
            "content": contents[idx],
            "metadata": chunk.get("metadata"),
        }
        if metadata:
            for key, value in metadata.items():
                if value is None:
                    continue
                payload[key] = value
        points.append(models.PointStruct(id=str(uuid.uuid4()), vector=vectors[idx], payload=payload))

    client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    logger.info("Stored %d vectors for filing %s.", len(points), filing_id)


def query_vector_store(
    query_text: str,
    *,
    filing_id: Optional[str] = None,
    top_k: int = 5,
    max_filings: int = 1,
    filters: Optional[Dict[str, Any]] = None,
) -> VectorSearchResult:
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")
    if max_filings <= 0:
        raise ValueError("max_filings must be greater than zero.")

    client = _client()
    try:
        init_collection()
    except Exception as exc:
        logger.error("Failed to ensure Qdrant collection: %s", exc, exc_info=True)
        raise RuntimeError("Vector collection unavailable.") from exc

    try:
        embedding_response = litellm.embedding(model=EMBEDDING_MODEL, input=[query_text])
    except Exception as exc:
        logger.error("Embedding generation for query failed: %s", exc, exc_info=True)
        raise RuntimeError("Embedding generation failed.") from exc

    query_vector = embedding_response.data[0]["embedding"]

    filter_conditions: List[models.FieldCondition] = []
    if filing_id:
        filter_conditions.append(
            models.FieldCondition(
                key="filing_id",
                match=models.MatchValue(value=filing_id),
            )
        )

    filters = filters or {}
    ticker = filters.get("ticker")
    if ticker:
        filter_conditions.append(models.FieldCondition(key="ticker", match=models.MatchValue(value=ticker)))

    sector = filters.get("sector")
    if sector:
        filter_conditions.append(models.FieldCondition(key="sector", match=models.MatchValue(value=sector)))

    sentiment = filters.get("sentiment")
    if sentiment:
        filter_conditions.append(models.FieldCondition(key="sentiment", match=models.MatchValue(value=sentiment)))

    min_ts = filters.get("min_published_at_ts")
    max_ts = filters.get("max_published_at_ts")
    if min_ts is not None or max_ts is not None:
        range_kwargs: Dict[str, float] = {}
        if min_ts is not None:
            range_kwargs["gte"] = float(min_ts)
        if max_ts is not None:
            range_kwargs["lte"] = float(max_ts)
        filter_conditions.append(models.FieldCondition(key="filed_at_ts", range=models.Range(**range_kwargs)))

    query_filter = models.Filter(must=filter_conditions) if filter_conditions else None

    search_limit = max(top_k * max_filings * 4, top_k)
    try:
        search_result = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=search_limit,
            with_payload=True,
        )
    except Exception as exc:
        logger.error("Qdrant search failed: %s", exc, exc_info=True)
        raise RuntimeError("Vector search failed.") from exc

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for point in search_result:
        raw_payload = dict(point.payload or {})
        normalized = _normalize_chunk_payload(raw_payload)
        normalized["score"] = float(point.score or 0.0)
        filing_key = str(normalized.get("filing_id") or "")
        if not filing_key:
            continue
        normalized.setdefault("id", normalized.get("chunk_id"))
        grouped.setdefault(filing_key, []).append(normalized)

    if filing_id and filing_id not in grouped:
        grouped[filing_id] = []

    ranked: List[Dict[str, Any]] = []
    for group_id, items in grouped.items():
        items.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
        top_item = items[0] if items else {}
        ranked.append(
            {
                "filing_id": group_id,
                "score": float(top_item.get("score") or 0.0),
                "chunk_count": len(items),
                "published_at": top_item.get("filed_at") or top_item.get("filed_at_iso"),
                "sentiment": top_item.get("sentiment"),
                "title": top_item.get("title") or top_item.get("report_name"),
            }
        )

    ranked.sort(key=lambda entry: entry.get("score", 0.0), reverse=True)
    selected_filing = filing_id or (ranked[0]["filing_id"] if ranked else None)
    selected_chunks: List[Dict[str, Any]] = []
    if selected_filing:
        selected_chunks = grouped.get(selected_filing, [])[:top_k]

    logger.info(
        "Retrieved %d chunks across %d filings (selected=%s).",
        sum(len(items) for items in grouped.values()),
        len(grouped),
        selected_filing,
    )
    return VectorSearchResult(
        filing_id=selected_filing,
        chunks=selected_chunks,
        related_filings=ranked[:max_filings],
    )


__all__ = ["store_chunk_vectors", "query_vector_store", "init_collection", "VectorSearchResult"]
