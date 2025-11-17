"""Simple in-memory cache for tenant SSO provider configs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from core.env import env_int
from core.logging import get_logger
from services.sso_provider_service import SsoProviderConfig, get_provider_config

logger = get_logger(__name__)


@dataclass
class _CacheEntry:
    value: Optional[SsoProviderConfig]
    expires_at: float


_PROVIDER_CACHE: Dict[str, _CacheEntry] = {}
_CACHE_TTL_SECONDS = env_int("SSO_PROVIDER_CACHE_TTL_SECONDS", 60, minimum=5)


def _cache_key(slug: str, provider_type: Optional[str]) -> str:
    slug_part = slug.strip().lower()
    type_part = (provider_type or "*").strip().lower()
    return f"{type_part}::{slug_part}"


def get_cached_provider_config(
    session: Session,
    *,
    slug: str,
    provider_type: Optional[str] = None,
) -> Optional[SsoProviderConfig]:
    """Return a cached provider config, reloading from DB once TTL expires."""

    key = _cache_key(slug, provider_type)
    now = time.time()
    entry = _PROVIDER_CACHE.get(key)
    if entry and entry.expires_at > now:
        return entry.value

    config = get_provider_config(session, slug, provider_type=provider_type)
    _PROVIDER_CACHE[key] = _CacheEntry(value=config, expires_at=now + _CACHE_TTL_SECONDS)
    return config


def invalidate_provider_cache(*, slug: Optional[str] = None, provider_type: Optional[str] = None) -> None:
    """Remove cached entries for the given slug/type (or everything if unspecified)."""

    if slug is None and provider_type is None:
        _PROVIDER_CACHE.clear()
        return

    slug_norm = slug.strip().lower() if slug else None
    type_norm = provider_type.strip().lower() if provider_type else None
    keys = list(_PROVIDER_CACHE.keys())
    for key in keys:
        type_part, _, slug_part = key.partition("::")
        if slug_norm and slug_part != slug_norm:
            continue
        if type_norm and type_part not in (type_norm, "*"):
            continue
        _PROVIDER_CACHE.pop(key, None)
