"""Prompt template for analysing news sentiment/topics."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You analyse Korean financial and market news. "
    "Identify sentiment (-1 to 1), core topics, and write concise rationale sentences. "
    "Each rationale sentence must be a complete Korean sentence (끝맺음 포함) under 160 characters. "
    "Return JSON only."
)

USER_PROMPT_TEMPLATE = """Summarise sentiment, topics, and rationale from the article.

Return JSON:
{{
  "sentiment": float between -1.0 and 1.0,
  "topics": ["keyword1", "keyword2", ...],
  "rationale": [
    "완결된 문장으로 된 요약 문장 1",
    "필요 시 두 번째 문장 (최대 2문장)"
  ]
}}

Guidelines:
- Focus on what the article means for Korean capital markets or corporates.
- Avoid 조각난 구절; 항상 주어·서술어가 있는 문장으로 작성하세요.

ARTICLE:
{article_text}
"""


def get_prompt(article_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(article_text=article_text)},
    ]


__all__ = ["get_prompt"]
