"""Health check helpers for LightMem dependencies."""

from __future__ import annotations

import time
from typing import Dict

from core.env import env_str
from core.logging import get_logger
from services.memory import long_term_store

logger = get_logger(__name__)


def check_session_store() -> Dict[str, object]:
    """Ping the Redis-backed session store (if configured)."""
    redis_url = env_str("LIGHTMEM_REDIS_URL")
    if not redis_url:
        return {
            "status": "skipped",
            "detail": "LIGHTMEM_REDIS_URL is not configured; falling back to in-memory store.",
        }

    try:  # pragma: no cover - optional dependency
        import redis  # type: ignore
    except ImportError:
        return {"status": "error", "detail": "redis python package is not installed."}

    start = time.perf_counter()
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=False)
        client.ping()
    except Exception as exc:  # pragma: no cover - network/credential failures
        logger.warning("LightMem Redis health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {"status": "ok", "latencyMs": latency_ms}


def check_qdrant_store() -> Dict[str, object]:
    """Ping the Qdrant-backed long term memory store."""
    try:
        client = long_term_store._client()  # reuse existing connection helper
    except Exception as exc:  # pragma: no cover - configuration issues
        logger.warning("LightMem Qdrant client init failed: %s", exc)
        return {"status": "error", "detail": str(exc)}

    if client is None:
        return {
            "status": "skipped",
            "detail": "Vector service client is not configured; long-term memory disabled.",
        }

    try:
        # list collections instead of creating when missing
        client.get_collections()
    except Exception as exc:  # pragma: no cover - network issues
        logger.warning("LightMem Qdrant health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}

    return {"status": "ok", "collection": long_term_store.LIGHTMEM_COLLECTION}


def lightmem_health_summary() -> Dict[str, object]:
    """Aggregate LightMem health statuses."""
    checks = {
        "sessionStore": check_session_store(),
        "longTermStore": check_qdrant_store(),
    }
    if any(result["status"] == "error" for result in checks.values()):
        status = "error"
    elif any(result["status"] == "skipped" for result in checks.values()):
        status = "degraded"
    else:
        status = "ok"
    return {"status": status, "checks": checks}


__all__ = ["check_session_store", "check_qdrant_store", "lightmem_health_summary"]
