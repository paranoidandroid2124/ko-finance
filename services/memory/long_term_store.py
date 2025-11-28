"""Qdrant-backed storage helpers for the LightMem long-term memory layer."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from qdrant_client import QdrantClient, models

from datetime import datetime, timezone
from services.memory.models import MemoryRecord
from services.embedding_utils import embed_text, EMBEDDING_MODEL

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LIGHTMEM_COLLECTION = os.getenv("LIGHTMEM_QDRANT_COLLECTION", "nuvien-memory-store")
LIGHTMEM_VECTOR_DIM = int(os.getenv("LIGHTMEM_VECTOR_DIM", "384"))
LIGHTMEM_DISTANCE = models.Distance.COSINE


def _client() -> QdrantClient:
    from services.vector_service import _client as rag_client  # reuse existing connection helper

    return rag_client()


def ensure_collection() -> None:
    client = _client()
    try:
        client.get_collection(collection_name=LIGHTMEM_COLLECTION)
    except Exception:
        logger.info("Creating LightMem Qdrant collection '%s'.", LIGHTMEM_COLLECTION)
        client.create_collection(
            collection_name=LIGHTMEM_COLLECTION,
            vectors_config=models.VectorParams(size=LIGHTMEM_VECTOR_DIM, distance=LIGHTMEM_DISTANCE),
        )


def persist_records(records: Sequence[MemoryRecord]) -> None:
    if not records:
        return
    ensure_collection()
    client = _client()
    points = []
    for record in records:
        points.append(
            models.PointStruct(
                id=record.record_id,
                vector=list(record.embedding),
                payload=record.as_payload(),
            )
        )
    client.upsert(collection_name=LIGHTMEM_COLLECTION, wait=True, points=points)


def search_records(
    *, tenant_id: str, user_id: str, query_text: str, limit: int
) -> Sequence[MemoryRecord]:
    ensure_collection()
    client = _client()
    query_vector = embed_text(query_text, model_name=EMBEDDING_MODEL)
    filters = models.Filter(
        must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
            models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id)),
        ]
    )
    search_result = client.search(
        collection_name=LIGHTMEM_COLLECTION,
        query_vector=query_vector,
        query_filter=filters,
        with_payload=True,
        limit=limit,
    )
    entries: List[MemoryRecord] = []
    for point in search_result:
        payload = point.payload or {}
        created_at_raw = payload.get("created_at")
        created_at = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw))
            except Exception:
                created_at = None
        try:
            entries.append(
                MemoryRecord(
                    tenant_id=str(payload.get("tenant_id")),
                    user_id=str(payload.get("user_id")),
                    topic=str(payload.get("topic") or ""),
                    summary=str(payload.get("summary") or ""),
                    embedding=point.vector or [],
                    importance_score=float(payload.get("importance_score") or point.score or 0.0),
                    created_at=created_at or datetime.now(timezone.utc),
                    updated_at=created_at or datetime.now(timezone.utc),
                    record_id=str(payload.get("record_id") or point.id),
                )
            )
        except Exception as exc:
            logger.debug("Skipping malformed payload from LightMem store: %s", exc)
    return entries
