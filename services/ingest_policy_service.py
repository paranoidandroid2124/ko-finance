"""Helpers for resolving ingest viewer fallback feature flags."""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from core.env import env_int
from models.ingest_viewer_flag import IngestViewerFlag

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = env_int("INGEST_VIEWER_FLAG_CACHE_SECONDS", 300, minimum=30)
_cached_flags: Dict[str, Tuple[bool, Optional[str]]] = {}
_cache_expiry: float = 0.0


def _load_flags(db: Session) -> Dict[str, Tuple[bool, Optional[str]]]:
    rows = db.query(IngestViewerFlag).all()
    flags: Dict[str, Tuple[bool, Optional[str]]] = {}
    for row in rows:
        flags[row.corp_code] = (bool(row.fallback_enabled), row.reason)
    logger.debug("Loaded %d ingest viewer fallback flag(s).", len(flags))
    return flags


def get_viewer_flag_map(db: Session, *, force_refresh: bool = False) -> Dict[str, Tuple[bool, Optional[str]]]:
    """Return a mapping of corp_code to (enabled, reason) tuples."""
    global _cached_flags, _cache_expiry
    now = time.time()
    if force_refresh or now >= _cache_expiry or not _cached_flags:
        _cached_flags = _load_flags(db)
        _cache_expiry = now + float(_CACHE_TTL_SECONDS)
    return _cached_flags


def viewer_fallback_state(
    db: Session,
    corp_code: Optional[str],
    *,
    force_refresh: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Return (enabled, reason) tuple for the provided corp_code."""
    if not corp_code:
        return True, None
    flags = get_viewer_flag_map(db, force_refresh=force_refresh)
    state = flags.get(corp_code)
    if state is None:
        return True, None
    return state


__all__ = ["get_viewer_flag_map", "viewer_fallback_state"]

