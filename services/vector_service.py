"""Interface to Qdrant vector store used by the RAG pipeline."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import litellm
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_CONNECT_RETRIES = int(os.getenv("QDRANT_CONNECT_RETRIES", "3"))
QDRANT_RETRY_DELAY_SEC = float(os.getenv("QDRANT_RETRY_DELAY_SEC", "1.5"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
VECTOR_DIMENSION = 1536
COLLECTION_NAME = "k-finance-rag-collection"

_qdrant_client: Optional[QdrantClient] = None


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


def store_chunk_vectors(filing_id: str, chunks: List[Dict[str, Any]]) -> None:
    if not chunks:
        logger.warning("No chunks provided for filing %s. Skipping vector store upsert.", filing_id)
        return

    client = _client()
    init_collection()

    contents: List[str] = []
    for chunk in chunks:
        raw_content = chunk.get("content", "")
        contents.append(raw_content if isinstance(raw_content, str) else str(raw_content))

    if not any(contents):
        logger.warning("All chunk contents are empty for filing %s.", filing_id)
        return

    try:
        embedding_response = litellm.embedding(model=EMBEDDING_MODEL, input=contents)
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc, exc_info=True)
        raise

    vectors = [item["embedding"] for item in embedding_response.data]
    points: List[models.PointStruct] = []
    for idx, chunk in enumerate(chunks):
        payload = {
            "filing_id": filing_id,
            "chunk_id": chunk.get("id"),
            "page_number": chunk.get("page_number"),
            "type": chunk.get("type"),
            "section": chunk.get("section"),
            "source": chunk.get("source"),
            "content": contents[idx],
            "metadata": chunk.get("metadata"),
        }
        points.append(models.PointStruct(id=str(uuid.uuid4()), vector=vectors[idx], payload=payload))

    client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    logger.info("Stored %d vectors for filing %s.", len(points), filing_id)


def query_vector_store(query_text: str, filing_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

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
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="filing_id",
                match=models.MatchValue(value=filing_id),
            )
        ]
    )

    try:
        search_result = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
    except Exception as exc:
        logger.error("Qdrant search failed: %s", exc, exc_info=True)
        raise RuntimeError("Vector search failed.") from exc

    chunks: List[Dict[str, Any]] = []
    for point in search_result:
        payload = dict(point.payload or {})
        payload["score"] = point.score
        chunks.append(payload)
    logger.info("Retrieved %d chunks for filing %s (top_k=%d).", len(chunks), filing_id, top_k)
    return chunks


__all__ = ["store_chunk_vectors", "query_vector_store", "init_collection"]
