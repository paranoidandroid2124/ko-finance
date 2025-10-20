"""Prompt template for classifying filings (M1)."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You are a compliance-focused assistant that classifies Korean financial filings. "
    "Return JSON only. If the category is unclear, respond with \"other\" and explain why."
)

USER_PROMPT_TEMPLATE = """Classify the filing excerpt below.

Categories:
[
  "capital_increase", "buyback", "cb_bw", "large_contract", "litigation",
  "governance", "audit_opinion", "periodic_report", "securities_registration",
  "insider_ownership", "correction", "other"
]

If the category is "capital_increase", add `"allocation": "rights"|"third_party"|"unknown"`.

Return JSON with:
{{
  "category": "...",
  "allocation": "...",  # optional
  "rationale": ["short supporting quotes"],
  "anchors": [{{"page": number, "quote": "..."}}]
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

