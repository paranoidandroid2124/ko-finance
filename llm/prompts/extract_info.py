"""Prompt template for extracting structured facts from filings."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You extract structured information from Korean corporate filings. "
    "Return JSON only. Preserve numeric precision and cite anchors."
)

USER_PROMPT_TEMPLATE = """From the filing excerpt, extract factual statements.

Return JSON:
{{
  "facts": [
    {{
      "field": "counterparty|amount|due_date|... (snake_case)",
      "value": "...",
      "unit": "...",
      "currency": "...",
      "anchor": {{"page": number, "quote": "short citation"}},
      "confidence": 0.0-1.0
    }}
  ],
  "notes": "optional analyst notes"
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

