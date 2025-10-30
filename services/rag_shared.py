"""Shared normalization helpers used by RAG services and routers."""

from __future__ import annotations

from typing import Any, Dict, Optional


def safe_int(value: Any) -> Optional[int]:
    """Best-effort conversion to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    """Best-effort conversion to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_reliability(value: Any) -> Optional[str]:
    """Normalize reliability inputs into high/medium/low buckets."""
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"high", "medium", "low"}:
            return lowered
        return None
    numeric = safe_float(value)
    if numeric is None:
        return None
    if numeric >= 0.66:
        return "high"
    if numeric >= 0.33:
        return "medium"
    return "low"


def _paragraph_id_from_context(chunk: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
    candidate = metadata.get("paragraph_id") or chunk.get("paragraph_id")
    if candidate:
        return str(candidate)
    for key in ("chunk_id", "id"):
        value = chunk.get(key)
        if value:
            return str(value)
    return None


def build_anchor_payload(chunk: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Assemble a normalized anchor payload suitable for downstream consumers."""
    anchor_source = metadata.get("anchor") or chunk.get("anchor")
    anchor: Dict[str, Any] = {}
    if isinstance(anchor_source, dict):
        anchor.update(anchor_source)

    paragraph_id = anchor.get("paragraph_id") or _paragraph_id_from_context(chunk, metadata)
    if paragraph_id:
        anchor["paragraph_id"] = str(paragraph_id)

    pdf_rect_source = anchor.get("pdf_rect")
    if not isinstance(pdf_rect_source, dict):
        pdf_rect_source = metadata.get("pdf_rect") if isinstance(metadata.get("pdf_rect"), dict) else None
    if isinstance(pdf_rect_source, dict):
        page = safe_int(pdf_rect_source.get("page") or chunk.get("page_number"))
        if page:
            anchor["pdf_rect"] = {
                "page": page,
                "x": safe_float(pdf_rect_source.get("x")) or 0.0,
                "y": safe_float(pdf_rect_source.get("y")) or 0.0,
                "width": safe_float(pdf_rect_source.get("width")) or 0.0,
                "height": safe_float(pdf_rect_source.get("height")) or 0.0,
            }

    similarity_source = (
        anchor.get("similarity")
        or metadata.get("similarity")
        or chunk.get("similarity")
        or chunk.get("score")
    )
    similarity_value = safe_float(similarity_source)
    if similarity_value is not None:
        anchor["similarity"] = similarity_value
    else:
        anchor.pop("similarity", None)

    return anchor or None


__all__ = ["build_anchor_payload", "normalize_reliability", "safe_float", "safe_int"]
