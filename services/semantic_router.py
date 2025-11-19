"""SemanticRouter orchestrates intent routing for chat queries."""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

from pydantic import ValidationError

from core.logging import get_logger
from llm import llm_service
from schemas.router import RouteAction, RouteDecision

logger = get_logger(__name__)

DEFAULT_BLOCK_PATTERNS: Sequence[str] = (
    # 명령형 · 즉시성 질문
    r"(지금|당장|오늘|내일)\s*(사도|팔아도|사면|팔면)\s*(될까|돼|되나요|됩니까)",
    r"(얼마|몇\s*원)\s*(가면|되면)\s*(팔|사|매도|매수)\s*(할까|해야\s*해|해야\s*하나)",
    # 직접 추천/지시 요구
    r"(종목|주식)\s*(추천\s*해|찍어\s*줘|골라\s*줘)",
    r"(사라|팔아라|존버)\s*라고\s*해줘",
    r"(매수|매도)\s*하라고\s*해줘",
    # 투기성·몰빵 표현
    r"(풀\s*매수|몰빵|레버리지)\s*(해도|가도|해볼까|괜찮아)",
    r"(떡상|떡락)\s*할\s*(거|까|듯)\s*같",
    r"(비중)\s*(확대|늘려|줄여|축소)\s*(해|할까|해야\s*해)",
)


class SemanticRouter:
    """High-level router that combines regex guardrails and LLM prompts."""

    def __init__(
        self,
        *,
        block_patterns: Optional[Sequence[str]] = None,
    ) -> None:
        patterns = block_patterns or DEFAULT_BLOCK_PATTERNS
        self._blocklist = tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)

    def route(self, question: str) -> RouteDecision:
        """Return a RouteDecision for the given natural-language question."""

        normalized = (question or "").strip()
        if not normalized:
            return self._fallback_decision("empty_query")

        blocked = self._match_blocklist(normalized)
        if blocked:
            return blocked

        payload = llm_service.route_chat_query(normalized)
        payload.pop("model_used", None)
        payload.pop("error", None)
        try:
            decision = RouteDecision.model_validate(payload)
        except ValidationError as exc:
            logger.warning("SemanticRouter validation failed: %s", exc, exc_info=True)
            return self._fallback_decision("router_validation_failed")

        return decision

    def _match_blocklist(self, question: str) -> Optional[RouteDecision]:
        triggered: List[str] = []
        for pattern in self._blocklist:
            match = pattern.search(question)
            if match:
                triggered.append(match.group(0))
        if not triggered:
            return None
        return RouteDecision(
            action=RouteAction.BLOCK_COMPLIANCE,
            reason="금융 규제 키워드 감지됨",
            confidence=1.0,
            blocked_phrases=triggered,
            metadata={"source": "regex_blocklist"},
        )

    def _fallback_decision(self, reason: str) -> RouteDecision:
        return RouteDecision(
            action=RouteAction.RAG_ANSWER,
            reason=reason,
            confidence=0.0,
            metadata={"fallback": True},
        )


DEFAULT_ROUTER = SemanticRouter()


def route_question(question: str) -> RouteDecision:
    """Convenience wrapper for the default SemanticRouter instance."""

    return DEFAULT_ROUTER.route(question)


__all__ = ["SemanticRouter", "DEFAULT_ROUTER", "route_question"]
