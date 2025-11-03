"""Guardrail helpers to prevent investment advice leakage."""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional, Tuple

DEFAULT_BANNED_PATTERNS = [
    r"(매수|매도)\s*(추천|권유)",
    r"투자\s*(조언|자문)",
    r"목표\s*가",
    r"손절\s*가",
    r"익절\s*가",
    r"buy\s+this\s+stock",
    r"\b(should|must)\s*(buy|sell)\b",
    r"\bstrong\s*(buy|sell)\b",
    r"\bprice\s*target\b",
    r"stop[-\s]?loss",
    r"take[-\s]?profit",
    r"sure\s*(win|thing)",
    r"guarantee[d]?\s+(profit|return)",
]

_DEFAULT_SAFE_MESSAGE = "투자 자문이나 매수·매도 권고는 제공되지 않습니다. 정보 제공 목적의 분석 질문만 부탁드립니다."

SAFE_MESSAGE = _DEFAULT_SAFE_MESSAGE
_CUSTOM_BLOCKLIST: List[str] = []


def _load_env_patterns() -> List[str]:
    raw = os.getenv("GUARDRAIL_BANNED_PATTERNS")
    if not raw:
        return []
    return [pattern.strip() for pattern in raw.split(",") if pattern.strip()]


def _compile_patterns(patterns: Iterable[str]) -> List[re.Pattern[str]]:
    compiled: List[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            continue
    return compiled


def _effective_blocklist() -> List[str]:
    return [*DEFAULT_BANNED_PATTERNS, *_load_env_patterns(), *_CUSTOM_BLOCKLIST]


BANNED_PATTERNS = _compile_patterns(_effective_blocklist())


def apply_answer_guard(answer: str) -> Tuple[str, Optional[str]]:
    """Return a sanitized answer and optional violation code."""
    if not answer:
        return answer, None
    for pattern in BANNED_PATTERNS:
        if pattern.search(answer):
            return SAFE_MESSAGE, f"guardrail_violation:{pattern.pattern}"
    return answer, None


def update_guardrail_blocklist(blocklist: Iterable[str]) -> None:
    """Override the runtime guardrail blocklist with administrator-provided patterns."""
    global _CUSTOM_BLOCKLIST, BANNED_PATTERNS
    _CUSTOM_BLOCKLIST = [pattern.strip() for pattern in blocklist if isinstance(pattern, str) and pattern.strip()]
    BANNED_PATTERNS = _compile_patterns(_effective_blocklist())


def update_safe_message(message: Optional[str]) -> None:
    """Update the fallback guardrail message used when responses are blocked."""
    global SAFE_MESSAGE
    SAFE_MESSAGE = message or _DEFAULT_SAFE_MESSAGE


def matched_blocklist_terms(text: str) -> List[str]:
    """Return the list of blocklist regex patterns that match the supplied text."""
    hits: List[str] = []
    for pattern in BANNED_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


__all__ = [
    "apply_answer_guard",
    "matched_blocklist_terms",
    "SAFE_MESSAGE",
    "update_guardrail_blocklist",
    "update_safe_message",
]
