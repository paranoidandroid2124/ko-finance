"""Guardrail helpers to prevent investment advice leakage."""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

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


def _load_custom_patterns() -> List[str]:
    raw = os.getenv("GUARDRAIL_BANNED_PATTERNS")
    if not raw:
        return []
    return [pattern.strip() for pattern in raw.split(",") if pattern.strip()]


BANNED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in (*DEFAULT_BANNED_PATTERNS, *_load_custom_patterns())
]

SAFE_MESSAGE = (
    "투자 자문이나 매수·매도 권고는 제공되지 않습니다. "
    "정보 제공 목적의 분석 질문만 부탁드립니다."
)


def apply_answer_guard(answer: str) -> Tuple[str, Optional[str]]:
    """Return a sanitized answer and optional violation code."""
    if not answer:
        return answer, None
    for pattern in BANNED_PATTERNS:
        if pattern.search(answer):
            return SAFE_MESSAGE, f"guardrail_violation:{pattern.pattern}"
    return answer, None


__all__ = ["apply_answer_guard", "SAFE_MESSAGE"]

