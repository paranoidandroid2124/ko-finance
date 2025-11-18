"""Utility script to update Qdrant payloads after sector slug changes.

Usage:
    python scripts/update_qdrant_sector_payload.py

Environment variables:
    QDRANT_HOST / QDRANT_PORT        : connection info (defaults: localhost / 6333)
    QDRANT_COLLECTION_NAME           : overrides the default RAG collection name

The slug mapping below can be extended if future migrations rename additional sectors.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple, cast

from qdrant_client import QdrantClient, models

DEFAULT_COLLECTION = "k-finance-rag-collection"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", DEFAULT_COLLECTION)
SCROLL_LIMIT = 256

# old_slug -> new_slug mapping
SECTOR_SLUG_MAPPING: Dict[str, str] = {
    "misc": "others",
}


def _update_sector_payload(client: QdrantClient, old_slug: str, new_slug: str) -> Tuple[int, int]:
    total_points = 0
    batches = 0
    offset = None
    filter_condition = models.Filter(
        must=[
            models.FieldCondition(
                key="sector",
                match=models.MatchValue(value=old_slug),
            )
        ]
    )

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=filter_condition,
            with_vectors=False,
            with_payload=False,
            limit=SCROLL_LIMIT,
            offset=offset,
        )
        if not points:
            break

        point_ids = [point.id for point in points]
        point_selector = models.PointIdsList(points=point_ids)
        client_ref = cast(Any, client)
        client_ref.set_payload(
            collection_name=COLLECTION_NAME,
            payload={"sector": new_slug},
            points=point_selector,
        )
        total_points += len(point_ids)
        batches += 1

    return total_points, batches


def main() -> None:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    print(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT} (collection={COLLECTION_NAME})")

    for old_slug, new_slug in SECTOR_SLUG_MAPPING.items():
        if old_slug == new_slug:
            continue
        updated, batches = _update_sector_payload(client, old_slug, new_slug)
        print(f"{old_slug} -> {new_slug}: updated {updated} points in {batches} batches")

    print("Sector payload update completed.")


if __name__ == "__main__":
    main()
