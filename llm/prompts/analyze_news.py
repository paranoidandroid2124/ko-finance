"""Prompt template for analysing news sentiment/topics."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You analyse Korean financial news. "
    "Identify sentiment (-1 to 1), key topics, and rationale sentences. "
    "Return JSON only."
)

USER_PROMPT_TEMPLATE = """Summarise sentiment, topics, and rationale from the article.

Return JSON:
{{
  "sentiment": float between -1.0 and 1.0,
  "topics": ["keyword1", "keyword2", ...],
  "rationale": ["short sentence 1", "short sentence 2", ...]
}}

ARTICLE:
{article_text}
"""


def get_prompt(article_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(article_text=article_text)},
    ]


__all__ = ["get_prompt"]

