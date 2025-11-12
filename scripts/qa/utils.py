"""Shared helpers for QA sampling and verification scripts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def coerce_int(value: Any) -> Optional[int]:
    """Best-effort conversion to int, returning None on failure."""

    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def load_chunks(raw: Any) -> List[Dict[str, Any]]:
    """Decode JSON/text chunk blobs into a list of dictionaries."""

    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [item for item in decoded if isinstance(item, dict)]
    return []


def load_urls(raw: Any) -> Dict[str, Any]:
    """Normalize stored URL metadata to a dictionary."""

    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, dict):
                return decoded
        except json.JSONDecodeError:
            return {}
    return {}


def format_datetime(value: Optional[datetime]) -> Optional[str]:
    """Return an ISO timestamp in UTC for the provided datetime."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


__all__ = ["coerce_int", "format_datetime", "load_chunks", "load_urls"]
