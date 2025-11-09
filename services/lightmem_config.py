"""Shared LightMem configuration helpers."""

from __future__ import annotations

import uuid
from typing import Optional

from core.env import env_int, env_str

DIGEST_RATE_LIMIT_PER_MINUTE = env_int("LIGHTMEM_DIGEST_RATE_LIMIT_PER_MINUTE", 60, minimum=1)
_DEFAULT_USER_ID_RAW = env_str("LIGHTMEM_DEFAULT_USER_ID")


def default_user_id() -> Optional[uuid.UUID]:
    """Return the cached default LightMem user id configured via environment."""
    if not _DEFAULT_USER_ID_RAW:
        return None
    try:
        return uuid.UUID(_DEFAULT_USER_ID_RAW)
    except (ValueError, TypeError):
        return None


__all__ = ["DIGEST_RATE_LIMIT_PER_MINUTE", "default_user_id"]
