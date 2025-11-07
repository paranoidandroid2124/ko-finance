"""Session-level summary storage used for the short-term memory layer."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from core.env import env_int, env_str
from core.logging import get_logger
from services.memory.crypto import decrypt, encrypt
from services.memory.models import SessionSummaryEntry

logger = get_logger(__name__)

UTC = timezone.utc


class SessionSummaryStore:
    """Abstraction over Redis (preferred) with an in-memory fallback.

    Parameters
    ----------
    default_ttl_minutes:
        TTL applied when the caller does not provide an explicit ``expires_at``.
        See ``MemoryRuntimeSettings`` for the default value (120 minutes).
    redis_url:
        Optional connection string. When missing, the store operates in
        in-memory mode which is suitable for local development and tests.
    """

    _KEY_TEMPLATE = "lightmem:session:{session_id}"

    def __init__(self, *, default_ttl_minutes: int, redis_url: Optional[str] = None):
        self._default_ttl = timedelta(minutes=default_ttl_minutes)
        self._redis = None
        self._local_store: Dict[str, Tuple[List[SessionSummaryEntry], datetime]] = {}
        if redis_url:
            try:  # pragma: no cover - optional dependency
                import redis

                self._redis = redis.Redis.from_url(redis_url, decode_responses=False)
            except ImportError:
                logger.warning("redis package not installed; falling back to in-memory session store.")
            except Exception as exc:
                logger.warning("Failed to initialise Redis session store (%s). Using in-memory fallback.", exc)

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------
    def _redis_key(self, session_id: str) -> str:
        return self._KEY_TEMPLATE.format(session_id=session_id)

    def _redis_save(self, session_id: str, entries: List[SessionSummaryEntry], ttl: timedelta) -> None:
        if self._redis is None:
            return
        payload = json.dumps([entry.as_dict() for entry in entries], ensure_ascii=False).encode("utf-8")
        data = encrypt(payload)
        key = self._redis_key(session_id)
        self._redis.setex(key, int(ttl.total_seconds()), data)

    def _redis_load(self, session_id: str) -> Optional[List[SessionSummaryEntry]]:
        if self._redis is None:
            return None
        raw = self._redis.get(self._redis_key(session_id))
        if not raw:
            return None
        try:
            decrypted = decrypt(raw)
            items = json.loads(decrypted.decode("utf-8"))
            return [SessionSummaryEntry.from_dict(item) for item in items]
        except Exception as exc:
            logger.warning("Failed to decode session summaries for %s: %s", session_id, exc)
            return None

    def _redis_delete(self, session_id: str) -> None:
        if self._redis is None:
            return
        self._redis.delete(self._redis_key(session_id))

    def _redis_scan_ids(self) -> Iterable[str]:
        if self._redis is None:
            return []
        pattern = self._KEY_TEMPLATE.format(session_id="*")
        for key in self._redis.scan_iter(match=pattern):
            key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            yield key_str.split(":", 2)[-1]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save(self, entry: SessionSummaryEntry) -> None:
        now = datetime.now(UTC)
        expires_at = entry.expires_at if entry.expires_at > now else now + self._default_ttl
        target = replace(entry, expires_at=expires_at, updated_at=now)

        ttl = expires_at - now
        if ttl.total_seconds() <= 0:
            ttl = self._default_ttl

        if self._redis is not None:
            existing = self._redis_load(target.session_id) or []
            updated_list = [item for item in existing if item.topic != target.topic]
            updated_list.append(target)
            self._redis_save(target.session_id, updated_list, ttl)
            return

        # In-memory fallback
        current_list, _ = self._local_store.get(target.session_id, ([], datetime.now(UTC)))
        filtered = [item for item in current_list if item.topic != target.topic]
        filtered.append(target)
        self._local_store[target.session_id] = (filtered, datetime.now(UTC) + ttl)

    def load(self, session_id: str) -> List[SessionSummaryEntry]:
        if self._redis is not None:
            entries = self._redis_load(session_id)
            return entries or []

        payload = self._local_store.get(session_id)
        if not payload:
            return []
        entries, expires_at = payload
        if datetime.now(UTC) > expires_at:
            self._local_store.pop(session_id, None)
            return []
        return entries

    def delete(self, session_id: str) -> None:
        if self._redis is not None:
            self._redis_delete(session_id)
            return
        self._local_store.pop(session_id, None)

    def iter_session_ids(self) -> Iterable[str]:
        if self._redis is not None:
            return list(self._redis_scan_ids())
        return list(self._local_store.keys())

    def purge_expired(self) -> None:
        """Remove expired entries from the in-memory fallback."""

        if self._redis is not None:
            return  # Redis handles TTL automatically
        now = datetime.now(UTC)
        expired_keys = [key for key, (_, exp) in self._local_store.items() if exp <= now]
        for key in expired_keys:
            self._local_store.pop(key, None)


def build_default_store() -> SessionSummaryStore:
    """Factory that initialises the store based on environment variables."""

    from services.memory.config import MemoryRuntimeSettings

    settings = MemoryRuntimeSettings.load()
    redis_url = env_str("LIGHTMEM_REDIS_URL")
    return SessionSummaryStore(default_ttl_minutes=settings.session_ttl_minutes, redis_url=redis_url)
