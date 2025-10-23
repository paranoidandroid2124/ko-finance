"""Prompt template for producing 5W1H summaries."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You write concise 5W1H summaries of Korean disclosures. "
    "Use professional Korean where possible. Return JSON only. "
    "If the excerpt lacks sufficient information, return the fixed fallback text exactly as instructed below."
)

USER_PROMPT_TEMPLATE = """Create a 5W1H summary and insight.

If any 5W1H element is missing, use the literal string "정보 없음".
If the excerpt is empty or contains no meaningful disclosure content, set every 5W1H field to "정보 없음",
set "insight" to "유효한 공시 본문이 제공되지 않아 요약이 불가능합니다.", and set "confidence_score" to 0.0.

Return JSON:
{{
  "who": "...",
  "what": "...",
  "when": "...",
  "where": "...",
  "how": "...",
  "why": "...",
  "insight": "...",
  "confidence_score": 0.0-1.0
}}

FILING EXCERPT:
{{FILING_MD_SNIPPET}}
"""


def get_prompt(snippet: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.replace("{{FILING_MD_SNIPPET}}", snippet)},
    ]


__all__ = ["get_prompt"]
