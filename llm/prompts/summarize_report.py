"""Prompt template for producing 5W1H summaries."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You write concise 5W1H summaries of Korean disclosures. "
    "Use professional Korean where possible. Return JSON only."
)

USER_PROMPT_TEMPLATE = """Create a 5W1H summary and insight.

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

