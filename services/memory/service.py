"""Facade combining sensory, short-term, and long-term memory helpers.

The goal of this initial scaffold is to provide a central place that other
modules (watchlist chat, admin flows) can depend on while we
iteratively wire in the concrete storage/retrieval pieces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Mapping, Optional, Sequence

from core.logging import get_logger
from services.memory.config import MemoryFeatureFlags, MemoryRuntimeSettings
from services.memory.long_term_store import search_records
from services.memory.models import MemoryRecord, SessionSummaryEntry
from services.memory.session_store import SessionSummaryStore, build_default_store
from services.lightmem.preprocessor import PreprocessedPrompt, compress_prompt

logger = get_logger(__name__)
UTC = timezone.utc


@dataclass(frozen=True)
class PromptComposition:
    """Bundle representing the ingredients for a final LLM prompt."""

    base_prompt: str
    compressed_prompt: PreprocessedPrompt
    session_summaries: Sequence[SessionSummaryEntry]
    long_term_records: Sequence[MemoryRecord]
    rag_snippets: Sequence[str]

    def build(self) -> str:
        """Render a human-readable prompt string.

        The layout is intentionally simple and can be replaced by a more
        sophisticated template once the data pipeline is in place.
        """

        sections = [
            "# 사용자 요청",
            self.compressed_prompt.text or self.base_prompt,
        ]
        if self.session_summaries:
            sections.append("# 최근 세션 요약")
            sections.extend(f"- {entry.topic}: {'; '.join(entry.highlights)}" for entry in self.session_summaries)
        if self.long_term_records:
            sections.append("# 사용자 장기 메모리")
            sections.extend(f"- {record.topic}: {record.summary}" for record in self.long_term_records)
        if self.rag_snippets:
            sections.append("# 참고 근거")
            sections.extend(f"- {snippet}" for snippet in self.rag_snippets)
        return "\n".join(sections)


class MemoryService:
    """Main entry point used by application code.

    Parameters
    ----------
    feature_flags:
        Toggle definitions loaded from environment/config.
    runtime_settings:
        Tunables such as TTL or retrieval counts.
    session_store:
        Object responsible for persisting short-term summaries.
    """

    def __init__(
        self,
        *,
        feature_flags: Optional[MemoryFeatureFlags] = None,
        runtime_settings: Optional[MemoryRuntimeSettings] = None,
        session_store: Optional[SessionSummaryStore] = None,
    ) -> None:
        self._feature_flags = feature_flags or MemoryFeatureFlags.load()
        self._runtime_settings = runtime_settings or MemoryRuntimeSettings.load()
        self._session_store = session_store or build_default_store()

    # ------------------------------------------------------------------
    # Feature flag helpers
    # ------------------------------------------------------------------
    def is_enabled(
        self,
        *,
        plan_memory_enabled: Optional[bool] = None,
        watchlist_context: bool = False,
    ) -> bool:
        if plan_memory_enabled is False:
            return False
        if plan_memory_enabled is True:
            return True
        if watchlist_context:
            return self._feature_flags.watchlist_enabled
        return self._feature_flags.default_enabled

    # ------------------------------------------------------------------
    # Sensory layer
    # ------------------------------------------------------------------
    def compress(self, prompt: str) -> PreprocessedPrompt:
        return compress_prompt(prompt, max_chars=self._runtime_settings.max_prompt_chars)

    # ------------------------------------------------------------------
    # Short-term memory layer
    # ------------------------------------------------------------------
    def save_session_summary(
        self,
        *,
        session_id: str,
        topic: str,
        highlights: Sequence[str],
        metadata: Optional[Mapping[str, str]] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        expiry = expires_at or (datetime.now(UTC) + timedelta(minutes=self._runtime_settings.session_ttl_minutes))
        entry = SessionSummaryEntry(
            session_id=session_id,
            topic=topic,
            highlights=list(highlights),
            metadata=dict(metadata or {}),
            expires_at=expiry,
        )
        self._session_store.save(entry)

    def get_session_summaries(self, session_id: str) -> Sequence[SessionSummaryEntry]:
        return self._session_store.load(session_id)

    # ------------------------------------------------------------------
    # Long-term memory layer (placeholder)
    # ------------------------------------------------------------------
    def retrieve_long_term(
        self,
        *,
        tenant_id: str,
        user_id: str,
        query: str,
        limit: Optional[int] = None,
    ) -> Sequence[MemoryRecord]:
        if not query.strip():
            return []
        try:
            return search_records(
                tenant_id=tenant_id,
                user_id=user_id,
                query_text=query,
                limit=limit or self._runtime_settings.retrieval_k,
            )
        except Exception as exc:
            logger.warning("Long-term memory retrieval failed; continuing without LTM. Error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Prompt composition
    # ------------------------------------------------------------------
    def compose_prompt(
        self,
        *,
        base_prompt: str,
        session_id: Optional[str],
        tenant_id: Optional[str],
        user_id: Optional[str],
        rag_snippets: Optional[Iterable[str]] = None,
        plan_memory_enabled: Optional[bool] = None,
        watchlist_context: bool = False,
    ) -> PromptComposition:
        if not self.is_enabled(
            plan_memory_enabled=plan_memory_enabled, watchlist_context=watchlist_context
        ):
            compressed = compress_prompt(base_prompt, max_chars=self._runtime_settings.max_prompt_chars)
            return PromptComposition(
                base_prompt=base_prompt,
                compressed_prompt=compressed,
                session_summaries=[],
                long_term_records=[],
                rag_snippets=list(rag_snippets or []),
            )

        compressed = compress_prompt(base_prompt, max_chars=self._runtime_settings.max_prompt_chars)
        summaries: Sequence[SessionSummaryEntry] = []
        if session_id:
            summaries = self.get_session_summaries(session_id)

        records: Sequence[MemoryRecord] = []
        if tenant_id and user_id and compressed.text:
            records = self.retrieve_long_term(
                tenant_id=tenant_id,
                user_id=user_id,
                query=compressed.text,
                limit=self._runtime_settings.retrieval_k,
            )

        return PromptComposition(
            base_prompt=base_prompt,
            compressed_prompt=compressed,
            session_summaries=summaries,
            long_term_records=records,
            rag_snippets=list(rag_snippets or []),
        )
