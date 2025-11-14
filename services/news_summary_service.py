"""On-demand news summary caching and generation helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING

from filelock import FileLock, Timeout

from core.env import env_int, env_str
from core.logging import get_logger
from llm import llm_service
from services.news_text import sanitize_news_summary

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from models.news import NewsSignal
else:  # fallback to Any to avoid importing the full models package during tests
    NewsSignal = Any  # type: ignore[assignment]

logger = get_logger(__name__)

_DEFAULT_CACHE_PATH = Path("uploads") / "news" / "summary_cache.json"
_CACHE_PATH = Path(env_str("NEWS_SUMMARY_CACHE_PATH") or _DEFAULT_CACHE_PATH)
_CACHE_ROOT = _CACHE_PATH.parent
_CACHE_TTL_MINUTES = env_int("NEWS_SUMMARY_CACHE_TTL_MINUTES", 1440, minimum=30)
_SUMMARY_MAX_CHARS = env_int("NEWS_SUMMARY_MAX_CHARS", 480, minimum=120)
_CACHE_LOCK_TIMEOUT = env_int("NEWS_SUMMARY_CACHE_LOCK_TIMEOUT", 5, minimum=1)


class NewsSummaryCacheBackend(Protocol):
    def load(self) -> Dict[str, Dict[str, Any]]:
        ...

    def save(self, cache: Dict[str, Dict[str, Any]]) -> None:
        ...


class FileNewsSummaryCacheBackend:
    def __init__(self, path: Path, *, lock_timeout: int) -> None:
        self._path = path
        self._lock_timeout = lock_timeout
        self._lock_path = path.parent / f"{path.name}.lock"

    def _acquire_lock(self) -> FileLock:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(str(self._lock_path), timeout=self._lock_timeout)

    def load(self) -> Dict[str, Dict[str, Any]]:
        lock = self._acquire_lock()
        try:
            with lock:
                if not self._path.exists():
                    return {}
                return json.loads(self._path.read_text(encoding="utf-8"))
        except Timeout as exc:  # pragma: no cover - defensive logging
            logger.warning("News summary cache lock timeout: %s", exc)
            return {}
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load news summary cache: %s", exc)
            return {}

    def save(self, cache: Dict[str, Dict[str, Any]]) -> None:
        lock = self._acquire_lock()
        try:
            with lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Timeout as exc:  # pragma: no cover - defensive logging
            logger.warning("News summary cache lock timeout on save: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to persist news summary cache: %s", exc)


_CACHE_BACKEND: NewsSummaryCacheBackend = FileNewsSummaryCacheBackend(
    _CACHE_PATH,
    lock_timeout=_CACHE_LOCK_TIMEOUT,
)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _cache_key(signal: NewsSignal) -> str:
    return str(getattr(signal, "id", None) or signal.url or signal.headline)


def _get_cached_summary(
    signal: NewsSignal,
    *,
    backend: NewsSummaryCacheBackend,
    ttl_minutes: int,
) -> Optional[str]:
    cache = backend.load()
    entry = cache.get(_cache_key(signal))
    if not isinstance(entry, dict):
        return None

    generated_at = _parse_timestamp(entry.get("generated_at"))
    if generated_at is None:
        return entry.get("summary")

    if datetime.now(timezone.utc) - generated_at > timedelta(minutes=ttl_minutes):
        return None
    return entry.get("summary")


def _store_cached_summary(
    signal: NewsSignal,
    summary: str,
    *,
    source: str,
    backend: NewsSummaryCacheBackend,
) -> None:
    cache = backend.load()
    cache[_cache_key(signal)] = {
        "summary": summary,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    backend.save(cache)


def _fallback_summary(signal: NewsSignal) -> str:
    fallback = f"{signal.headline}".strip()
    if not fallback:
        fallback = "요약이 준비되는 중입니다."
    return fallback[:_SUMMARY_MAX_CHARS]


def _generate_summary_via_llm(signal: NewsSignal, *, llm_client=llm_service) -> Optional[str]:
    article_context_parts = [
        f"Headline: {signal.headline}",
    ]
    if signal.summary:
        article_context_parts.append(f"Feed summary: {signal.summary}")
    if signal.evidence and isinstance(signal.evidence, dict):
        rationale = signal.evidence.get("rationale")
        if isinstance(rationale, str) and rationale.strip():
            article_context_parts.append(f"Existing rationale: {rationale}")

    article_context = "\n".join(part for part in article_context_parts if part)
    if not article_context:
        return None

    analysis = llm_client.analyze_news_article(article_context)
    if not isinstance(analysis, dict):
        return None
    rationale = analysis.get("rationale") or analysis.get("summary")
    if isinstance(rationale, str):
        return sanitize_news_summary(rationale, max_chars=_SUMMARY_MAX_CHARS)
    return None


def get_or_generate_summary(
    signal: NewsSignal,
    *,
    refresh: bool = False,
    cache_backend: Optional[NewsSummaryCacheBackend] = None,
    llm_client=llm_service,
    cache_ttl_minutes: Optional[int] = None,
) -> str:
    """
    Return a cached or freshly generated summary for a news signal.

    The function respects the on-disk cache, reuses feed-provided summaries when available,
    and falls back to LLM generation using existing analysis context.
    """

    backend = cache_backend or _CACHE_BACKEND
    ttl_minutes = cache_ttl_minutes or _CACHE_TTL_MINUTES

    if not refresh:
        cached = _get_cached_summary(signal, backend=backend, ttl_minutes=ttl_minutes)
        if isinstance(cached, str) and cached.strip():
            return cached.strip()

    candidates: List[tuple[str, str]] = []
    if signal.summary:
        feed_summary = sanitize_news_summary(signal.summary, max_chars=_SUMMARY_MAX_CHARS)
        if feed_summary:
            candidates.append((feed_summary, "feed_summary"))

    evidence = getattr(signal, "evidence", None)
    if isinstance(evidence, dict):
        rationale = evidence.get("rationale")
        if isinstance(rationale, str):
            rationale_summary = sanitize_news_summary(rationale, max_chars=_SUMMARY_MAX_CHARS)
            if rationale_summary:
                candidates.append((rationale_summary, "analysis_rationale"))

    for summary_text, source in candidates:
        _store_cached_summary(signal, summary_text, source=source, backend=backend)
        return summary_text

    generated = _generate_summary_via_llm(signal, llm_client=llm_client)
    if generated:
        _store_cached_summary(signal, generated, source="llm_generated", backend=backend)
        return generated

    fallback = _fallback_summary(signal)
    _store_cached_summary(signal, fallback, source="fallback", backend=backend)
    return fallback


__all__ = ["FileNewsSummaryCacheBackend", "get_or_generate_summary"]
