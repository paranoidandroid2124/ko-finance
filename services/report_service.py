"""Orchestrates multi-source context for investment memo generation."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from core.logging import get_logger
from database import SessionLocal
from llm import llm_service
from services import market_data, rag_service, report_repository


UUIDLike = Optional[Union[str, uuid.UUID]]

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReportMemoResult:
    content: str
    sources: List[Dict[str, str]]
    chart_payload: Optional[Dict[str, Any]]
    report_id: Optional[uuid.UUID] = None


class ReportService:
    """Phase 4 report orchestrator used by Commander TOOL_REPORT."""

    def __init__(self, *, news_limit: int = 5) -> None:
        self.news_limit = news_limit

    async def generate_investment_memo(
        self,
        ticker: str,
        *,
        user_id: UUIDLike = None,
        org_id: UUIDLike = None,
        title: Optional[str] = None,
    ) -> ReportMemoResult:
        """Fetch context in parallel and ask the LLM for a memo."""

        normalized = (ticker or "").strip()
        if not normalized:
            raise ValueError("ticker_required")

        news_results, peer_snapshot = await asyncio.gather(
            self._retrieve_refined_context(normalized),
            self._fetch_market_snapshot(normalized),
        )
        context = self._build_context(normalized, news_results, peer_snapshot)
        memo_content = await llm_service.write_investment_memo(normalized, context)
        sources = self._build_sources(news_results)
        memo_with_citations = self._inject_citations(memo_content, sources)
        report_record = self._persist_report(
            ticker=normalized,
            title=title or f"Investment Memo: {normalized}",
            content=memo_with_citations,
            sources=sources,
            user_id=user_id,
            org_id=org_id,
        )
        return ReportMemoResult(
            content=memo_with_citations,
            sources=sources,
            chart_payload=peer_snapshot,
            report_id=report_record.id if report_record else None,
        )

    async def _retrieve_refined_context(self, ticker: str) -> List[Dict[str, Any]]:
        """Advanced RAG querying with multi-aspect expansion and dedupe."""

        queries = [
            f"{ticker} latest quarterly earnings and financial results",
            f"{ticker} major investment risks and competitors",
            f"{ticker} future growth outlook and market sentiment",
        ]

        async def _run_query(query: str) -> List[Dict[str, Any]]:
            def _task() -> List[Dict[str, Any]]:
                try:
                    return rag_service.search_news_summaries(
                        query,
                        ticker=ticker,
                        limit=min(5, self.news_limit),
                    )
                except Exception as exc:  # pragma: no cover - network best-effort
                    logger.warning("News search failed for %s (query=%s): %s", ticker, query, exc, exc_info=True)
                    return []

            return await asyncio.to_thread(_task)

        results_lists = await asyncio.gather(*[_run_query(query) for query in queries])

        seen_urls: set[str] = set()
        unique_docs: List[Dict[str, Any]] = []
        for doc in (entry for sublist in results_lists for entry in sublist):
            url = ""
            if isinstance(doc, dict):
                url = (
                    doc.get("url")
                    or doc.get("viewer_url")
                    or doc.get("article_url")
                    or doc.get("source_url")
                    or ""
                ).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique_docs.append(doc)

        def _sort_key(entry: Dict[str, Any]) -> str:
            raw_date = (
                entry.get("published_at")
                or entry.get("date")
                or entry.get("publishedAt")
                or ""
            )
            return str(raw_date)

        unique_docs.sort(key=_sort_key, reverse=True)
        return unique_docs[: min(15, len(unique_docs))]

    async def _fetch_market_snapshot(self, ticker: str) -> Optional[Dict[str, Any]]:
        def _task() -> Optional[Dict[str, Any]]:
            session = SessionLocal()
            try:
                return market_data.build_peer_comparison(session, ticker)
            except Exception as exc:  # pragma: no cover - DB best-effort
                logger.debug("Peer comparison unavailable for %s: %s", ticker, exc, exc_info=True)
                return None
            finally:
                session.close()

        return await asyncio.to_thread(_task)

    def _build_context(
        self,
        ticker: str,
        news_data: List[Dict[str, Any]],
        peer_snapshot: Optional[Dict[str, Any]],
    ) -> str:
        news_section = self._format_news_section(news_data)
        market_section = self._format_market_section(peer_snapshot)
        return (
            f"[Target Company]: {ticker}\n\n"
            "[Recent News & Issues]\n"
            f"{news_section}\n\n"
            "[Market & Peer Signals]\n"
            f"{market_section}"
        ).strip()

    def _format_news_section(self, news_data: List[Dict[str, Any]]) -> str:
        if not news_data:
            return "- 최근 하이라이트 뉴스 없음"

        lines: List[str] = []
        for entry in news_data:
            title = (entry.get("title") or entry.get("source") or "뉴스").strip()
            summary = (entry.get("summary") or "").strip()
            published = (entry.get("published_at") or entry.get("date") or "N/A").split("T")[0]
            sentiment = entry.get("sentiment_label") or ""
            sentiment_part = f" · Sentiment: {sentiment}" if sentiment else ""
            if summary:
                lines.append(f"- {published}: {title}{sentiment_part}\n  {summary}")
            else:
                lines.append(f"- {published}: {title}{sentiment_part}")
            if len(lines) >= self.news_limit:
                break

        return "\n".join(lines)

    def _format_market_section(self, snapshot: Optional[Dict[str, Any]]) -> str:
        if not snapshot:
            return "- 시장/피어 비교 지표 없음"

        lines: List[str] = []
        label = snapshot.get("label") or snapshot.get("ticker")
        interpretation = snapshot.get("interpretation")
        if label:
            lines.append(f"- 기준 종목: {label} ({snapshot.get('ticker')})")
        if interpretation:
            lines.append(f"- 요약 해석: {interpretation}")

        latest_cards = snapshot.get("latest") or []
        if latest_cards:
            latest_parts = []
            for card in latest_cards:
                ticker = card.get("ticker")
                name = card.get("label") or ticker
                value = card.get("value")
                if name and isinstance(value, (int, float)):
                    latest_parts.append(f"{name}({ticker}): {round(value, 2)}%")
            if latest_parts:
                lines.append("- 최근 성과: " + ", ".join(latest_parts))

        correlations = [
            entry
            for entry in snapshot.get("correlations") or []
            if isinstance(entry.get("value"), (int, float))
        ]
        if correlations:
            correlations.sort(key=lambda item: abs(item["value"]), reverse=True)
            corr_parts = [
                f"{item.get('label') or item.get('ticker')}: {item['value']}"
                for item in correlations[:3]
            ]
            if corr_parts:
                lines.append("- 상관계수 Top: " + ", ".join(corr_parts))

        value_chain_summary = snapshot.get("valueChainSummary")
        if value_chain_summary:
            lines.append(f"- Value Chain: {value_chain_summary}")

        peers = snapshot.get("peers") or []
        if peers:
            peer_list = ", ".join(
                f"{entry.get('label')}({entry.get('ticker')})"
                for entry in peers[:4]
                if entry.get("ticker")
            )
            if peer_list:
                lines.append(f"- 비교 대상: {peer_list}")

        return "\n".join(lines) if lines else "- 시장 시그널 없음"

    def _build_sources(self, news_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        sources: List[Dict[str, str]] = []
        for idx, entry in enumerate(news_data, start=1):
            title = (entry.get("title") or entry.get("source") or "").strip()
            url = (entry.get("url") or entry.get("viewer_url") or entry.get("article_url") or "").strip()
            published = (entry.get("published_at") or entry.get("date") or "").split("T")[0]
            if not title or not url:
                continue
            sources.append(
                {
                    "index": idx,
                    "title": title,
                    "url": url,
                    "date": published or "N/A",
                }
            )
            if len(sources) >= self.news_limit:
                break
        return sources

    def _inject_citations(self, content: str, sources: List[Dict[str, str]]) -> str:
        if not sources or not content.strip():
            return content
        lines = content.splitlines()
        source_idx = 0
        for i, line in enumerate(lines):
            if source_idx >= len(sources):
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            url = sources[source_idx].get("url")
            display_index = source_idx + 1
            if url:
                lines[i] = f"{line} [{display_index}]({url})"
                source_idx += 1
        return "\n".join(lines)

    def _persist_report(
        self,
        *,
        ticker: str,
        title: str,
        content: str,
        sources: List[Dict[str, str]],
        user_id: UUIDLike,
        org_id: UUIDLike,
    ):
        user_uuid = self._coerce_uuid(user_id)
        if user_uuid is None:
            return None
        org_uuid = self._coerce_uuid(org_id)
        try:
            return report_repository.create_report_record(
                user_id=user_uuid,
                org_id=org_uuid,
                ticker=ticker,
                title=title,
                content_md=content,
                sources=sources,
            )
        except Exception as exc:  # pragma: no cover - persistence best-effort
            logger.warning("Failed to persist report for %s: %s", user_uuid, exc, exc_info=True)
            return None

    @staticmethod
    def _coerce_uuid(value: UUIDLike) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError):
            return None


__all__ = ["ReportService", "ReportMemoResult"]
