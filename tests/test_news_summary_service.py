from __future__ import annotations

import copy
import importlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from services import news_summary_service as svc


class InMemoryCacheBackend:
    def __init__(self, initial: Dict[str, Dict[str, Any]] | None = None) -> None:
        self.storage: Dict[str, Dict[str, Any]] = initial or {}

    def load(self) -> Dict[str, Dict[str, Any]]:
        return copy.deepcopy(self.storage)

    def save(self, cache: Dict[str, Dict[str, Any]]) -> None:
        self.storage = copy.deepcopy(cache)


class DummyLLM:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_news_article(self, context: str) -> Dict[str, str]:
        self.calls += 1
        return {"rationale": f"LLM:{context.splitlines()[0]}"}


def test_cached_summary_expires_and_refreshes() -> None:
    backend = InMemoryCacheBackend(
        {
            "id-1": {
                "summary": "stale summary",
                "source": "feed_summary",
                "generated_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
            }
        }
    )
    signal = SimpleNamespace(
        id="id-1",
        url=None,
        headline="Fresh Headline",
        summary="새로운 요약입니다.",
        evidence=None,
    )

    result = svc.get_or_generate_summary(
        signal,
        cache_backend=backend,
        cache_ttl_minutes=1,
    )

    assert result == "새로운 요약입니다."
    cached = backend.storage["id-1"]
    assert cached["summary"] == "새로운 요약입니다."
    assert cached["source"] == "feed_summary"


def test_llm_fallback_generates_summary() -> None:
    backend = InMemoryCacheBackend()
    llm = DummyLLM()
    signal = SimpleNamespace(
        id=None,
        url="https://example.com/news",
        headline="LLM Needed",
        summary=None,
        evidence=None,
    )

    result = svc.get_or_generate_summary(
        signal,
        cache_backend=backend,
        llm_client=llm,
        refresh=True,
    )

    assert result.startswith("LLM:")
    assert llm.calls == 1
    cache_values = list(backend.storage.values())
    assert cache_values, "LLM summary should be cached"
    assert cache_values[0]["source"] == "llm_generated"


def test_default_backend_respects_env_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    cache_path = tmp_path / "news" / "custom_cache.json"
    monkeypatch.setenv("NEWS_SUMMARY_CACHE_PATH", str(cache_path))
    reloaded = importlib.reload(svc)
    try:
        signal = SimpleNamespace(
            id="env-test",
            url=None,
            headline="Env override",
            summary="요약은 피드에서 제공합니다.",
            evidence=None,
        )
        result = reloaded.get_or_generate_summary(signal)
        assert result == "요약은 피드에서 제공합니다."
        assert cache_path.exists()
        stored = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "env-test" in stored
        assert stored["env-test"]["source"] == "feed_summary"
    finally:
        monkeypatch.delenv("NEWS_SUMMARY_CACHE_PATH", raising=False)
        importlib.reload(reloaded)
