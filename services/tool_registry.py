"""Shared registry describing commander tool metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from schemas.router import PaywallTier, UiContainer


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable metadata describing a commander tool."""

    tool_id: str
    call_name: str
    intent: str
    title: str
    description: str
    ui_container: UiContainer
    paywall: PaywallTier
    teaser_behavior: str = "inline"
    requires_context: tuple[str, ...] = ()
    memory_slots: tuple[str, ...] = ()


_TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    "event_study": ToolDefinition(
        tool_id="event_study",
        call_name="event_study.query",
        intent="event_study",
        title="Event Study",
        description="실적발표 · 유상증자 등 이벤트 이후의 CAR/CAAR 패턴을 계산합니다.",
        ui_container=UiContainer.OVERLAY,
        paywall=PaywallTier.PRO,
        teaser_behavior="blur",
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "disclosure_viewer": ToolDefinition(
        tool_id="disclosure_viewer",
        call_name="disclosure.viewer",
        intent="disclosure_lookup",
        title="지능형 공시 뷰어",
        description="공시 원문에서 중요한 문단을 찾아 하이라이트로 이동합니다.",
        ui_container=UiContainer.SIDE_PANEL,
        paywall=PaywallTier.STARTER,
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "quant_screener": ToolDefinition(
        tool_id="quant_screener",
        call_name="quant.screener",
        intent="quant_screen",
        title="퀀트 스크리너",
        description="자연어 필터로 저평가 종목·마진 개선 종목 등을 찾아줍니다.",
        ui_container=UiContainer.OVERLAY,
        paywall=PaywallTier.PRO,
        teaser_behavior="blur",
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "snapshot": ToolDefinition(
        tool_id="snapshot",
        call_name="snapshot.company",
        intent="company_snapshot",
        title="기업 Snapshot",
        description="시세·재무제표·주요 주주 현황을 카드 형태로 요약합니다.",
        ui_container=UiContainer.INLINE_CARD,
        paywall=PaywallTier.FREE,
        requires_context=("tenant.snapshot",),
    ),
    "market_briefing": ToolDefinition(
        tool_id="market_briefing",
        call_name="market.briefing",
        intent="market_briefing",
        title="AI 마켓 브리핑",
        description="장 마감 후 시황과 뉴스를 요약해 보여줍니다.",
        ui_container=UiContainer.INLINE_CARD,
        paywall=PaywallTier.FREE,
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "news_insights": ToolDefinition(
        tool_id="news_insights",
        call_name="news.rag",
        intent="news_insights",
        title="뉴스 리포터",
        description="최근 뉴스 요약과 신호를 카드 형태로 제공합니다.",
        ui_container=UiContainer.OVERLAY,
        paywall=PaywallTier.STARTER,
        teaser_behavior="blur",
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "peer_compare": ToolDefinition(
        tool_id="peer_compare",
        call_name="peer.compare",
        intent="peer_compare",
        title="Peer 비교",
        description="동종 업계와의 상대 수익률·상관관계를 분석합니다.",
        ui_container=UiContainer.OVERLAY,
        paywall=PaywallTier.PRO,
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "investment_report": ToolDefinition(
        tool_id="investment_report",
        call_name="report.generate",
        intent="investment_report",
        title="투자 메모 리포트",
        description="뉴스·피어 데이터를 병합해 Markdown 투자 메모를 작성합니다.",
        ui_container=UiContainer.OVERLAY,
        paywall=PaywallTier.PRO,
        teaser_behavior="blur",
        requires_context=("tenant.snapshot", "lightmem.summary"),
        memory_slots=("lightmem.summary",),
    ),
    "news_insights": ToolDefinition(
        tool_id="news_insights",
        call_name="news.rag",
        intent="news_insights",
        title="뉴스 리포터",
        description="최근 뉴스 요약과 신호를 카드 형태로 제공합니다.",
        ui_container=UiContainer.OVERLAY,
        paywall=PaywallTier.STARTER,
        teaser_behavior="blur",
        requires_context=("tenant.snapshot",),
        memory_slots=("lightmem.summary",),
    ),
    "rag_answer": ToolDefinition(
        tool_id="rag_answer",
        call_name="rag.answer",
        intent="rag_answer",
        title="RAG Answer",
        description="표준 문서 검색 기반 Q&A를 실행합니다.",
        ui_container=UiContainer.INLINE_CARD,
        paywall=PaywallTier.FREE,
        requires_context=(),
    ),
    "compliance_block": ToolDefinition(
        tool_id="compliance_block",
        call_name="compliance.block",
        intent="compliance_block",
        title="Compliance Block",
        description="규제 위반 문구가 감지되었을 때 응답을 차단합니다.",
        ui_container=UiContainer.INLINE_CARD,
        paywall=PaywallTier.FREE,
        requires_context=(),
    ),
}

_CALL_NAME_INDEX = {tool.call_name: tool for tool in _TOOL_DEFINITIONS.values()}


def list_tools() -> Iterable[ToolDefinition]:
    """Return an iterable of all registered tool definitions."""

    return _TOOL_DEFINITIONS.values()


def resolve_tool_by_call(call_name: str) -> Optional[ToolDefinition]:
    """Return the tool definition for a tool call name."""

    return _CALL_NAME_INDEX.get(call_name)


def resolve_tool(tool_id: str) -> Optional[ToolDefinition]:
    """Lookup a tool by its identifier."""

    return _TOOL_DEFINITIONS.get(tool_id)


__all__ = [
    "ToolDefinition",
    "list_tools",
    "resolve_tool",
    "resolve_tool_by_call",
]
