"""Helpers for building chunk representations shared by PDF/XML parsers."""

from __future__ import annotations

from typing import Any, Dict, Optional


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def build_chunk(
    chunk_id: str,
    *,
    chunk_type: str,
    content: str,
    section: str,
    source: str,
    page_number: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    chunk: Dict[str, Any] = {
        "id": chunk_id,
        "type": chunk_type,
        "content": content,
        "page_number": page_number,
        "section": section,
        "source": source,
    }
    if metadata:
        chunk["metadata"] = metadata
    return chunk

