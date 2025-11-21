"""Prompt template for the Front Door Guard query classifier."""

from __future__ import annotations

from textwrap import dedent
from typing import Dict, List


CLASSIFIER_INSTRUCTIONS = dedent(
    """
    너는 금융/투자/경제에 특화된 Nuvien의 질의 분류기다.
    Classify the user's query into exactly one of:
    - "chitchat": 인사, 자기소개 등 AI의 정체/persona를 묻는 말.
    - "financial_query": 주식/기업/시장/경제/투자/실적/공시/재무 관련 질문.
    - "out_of_domain": 그 외 모든 주제(수학·과학·역사·프로그램 등) 혹은 금융 무관.

    Respond with exactly one JSON object (no commentary):
    {"category": "chitchat|financial_query|out_of_domain"}
    """
).strip()


def get_prompt(user_query: str) -> List[Dict[str, str]]:
    """Build a minimal, JSON-only classification prompt."""

    normalized = (user_query or "").strip()
    user_content = f'User Query: "{normalized}"'
    return [
        {"role": "system", "content": CLASSIFIER_INSTRUCTIONS},
        {"role": "user", "content": user_content},
    ]


__all__ = ["get_prompt"]
