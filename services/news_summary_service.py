"""On-demand news summary caching and generation helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.env import env_int
from core.logging import get_logger
from models.news import NewsSignal
from services.news_text import sanitize_news_summary
from llm import llm_service

logger = get_logger(__name__)

_CACHE_ROOT = Path("uploads") / "news"
_CACHE_PATH = _CACHE_ROOT / "summary_cache.json"
_CACHE_TTL_MINUTES = env_int("NEWS_SUMMARY_CACHE_TTL_MINUTES", 1440, minimum=30)
_SUMMARY_MAX_CHARS = env_int("NEWS_SUMMARY_MAX_CHARS", 480, minimum=120)


def _load_cache() -> Dict[str, Dict[str, Any]]:
    if not _CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Failed to load news summary cache: %s", exc)
        return {}


def _save_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    try:
        _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Failed to persist news summary cache: %s", exc)


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


def _get_cached_summary(signal: NewsSignal) -> Optional[str]:
    cache = _load_cache()
    entry = cache.get(_cache_key(signal))
    if not isinstance(entry, dict):
        return None

    generated_at = _parse_timestamp(entry.get("generated_at"))
    if generated_at is None:
        return entry.get("summary")

    if datetime.now(timezone.utc) - generated_at > timedelta(minutes=_CACHE_TTL_MINUTES):
        return None
    return entry.get("summary")


def _store_cached_summary(signal: NewsSignal, summary: str, *, source: str) -> None:
    cache = _load_cache()
    cache[_cache_key(signal)] = {
        "summary": summary,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_cache(cache)


def _fallback_summary(signal: NewsSignal) -> str:
    fallback = f"{signal.headline}".strip()
    if not fallback:
        fallback = "요약이 준비되는 중입니다."
    return fallback[:_SUMMARY_MAX_CHARS]


def _generate_summary_via_llm(signal: NewsSignal) -> Optional[str]:
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

    analysis = llm_service.analyze_news_article(article_context)
    if not isinstance(analysis, dict):
        return None
    rationale = analysis.get("rationale") or analysis.get("summary")
    if isinstance(rationale, str):
        return sanitize_news_summary(rationale, max_chars=_SUMMARY_MAX_CHARS)
    return None


def get_or_generate_summary(signal: NewsSignal, *, refresh: bool = False) -> str:
    """
    Return a cached or freshly generated summary for a news signal.

    The function respects the on-disk cache, reuses feed-provided summaries when available,
    and falls back to LLM generation using existing analysis context.
    """

    if not refresh:
        cached = _get_cached_summary(signal)
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
        _store_cached_summary(signal, summary_text, source=source)
        return summary_text

    generated = _generate_summary_via_llm(signal)
    if generated:
        _store_cached_summary(signal, generated, source="llm_generated")
        return generated

    fallback = _fallback_summary(signal)
    _store_cached_summary(signal, fallback, source="fallback")
    return fallback


__all__ = ["get_or_generate_summary"]
