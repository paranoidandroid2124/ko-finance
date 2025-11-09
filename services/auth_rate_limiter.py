"""Redis-backed rate limiter for authentication workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from core.env import env_int, env_str
from core.logging import get_logger

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

logger = get_logger(__name__)

_REDIS_URL = env_str("AUTH_RATE_LIMIT_REDIS_URL") or env_str("LIGHTMEM_RATE_LIMIT_REDIS_URL")
_KEY_PREFIX = env_str("AUTH_RATE_LIMIT_PREFIX") or "auth"
_CLIENT: Optional["redis.Redis"] = None  # type: ignore[name-defined]
_CLIENT_ERROR_LOGGED = False


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: Optional[int]
    reset_at: Optional[datetime]
    backend_error: bool = False


def _get_client() -> Optional["redis.Redis"]:  # type: ignore[name-defined]
    global _CLIENT, _CLIENT_ERROR_LOGGED  # pylint: disable=global-statement
    if _CLIENT is not None:
        return _CLIENT
    if not _REDIS_URL or redis is None:
        logger.debug("Auth rate limiter redis_url missing or redis unavailable.")
        return None
    try:
        _CLIENT = redis.Redis.from_url(_REDIS_URL, decode_responses=False)
    except Exception as exc:  # pragma: no cover
        if not _CLIENT_ERROR_LOGGED:
            logger.warning("Auth rate limiter Redis init failed: %s", exc)
            _CLIENT_ERROR_LOGGED = True
        _CLIENT = None
    return _CLIENT


def check_limit(
    scope: str,
    identifier: Optional[str],
    *,
    limit: int,
    window_seconds: int = 60,
    weight: int = 1,
) -> RateLimitResult:
    if limit <= 0 or window_seconds <= 0 or weight <= 0:
        return RateLimitResult(allowed=True, remaining=None, reset_at=None)

    client = _get_client()
    if client is None:
        return RateLimitResult(allowed=True, remaining=None, reset_at=None, backend_error=True)

    key = f"{_KEY_PREFIX}:{scope}:{identifier or 'global'}"
    try:
        pipeline = client.pipeline()
        pipeline.incrby(key, weight)
        pipeline.ttl(key)
        count, ttl = pipeline.execute()
        if ttl is None or ttl < 0:
            client.expire(key, window_seconds)
            ttl = window_seconds
        allowed = int(count) <= limit
        remaining = max(limit - int(count), 0)
        reset_at = datetime.now(timezone.utc) + timedelta(seconds=max(int(ttl), 0))
        return RateLimitResult(allowed=allowed, remaining=remaining, reset_at=reset_at)
    except Exception as exc:  # pragma: no cover
        logger.warning("Auth rate limiter failed for %s:%s - %s", scope, identifier, exc, exc_info=True)
        return RateLimitResult(allowed=True, remaining=None, reset_at=None, backend_error=True)


__all__ = ["RateLimitResult", "check_limit"]
