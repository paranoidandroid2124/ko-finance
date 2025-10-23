"""Prompt template for classifying filings (M1)."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You are a compliance-focused assistant that classifies Korean financial filings. "
    "Return JSON only. Use the predefined Korean labels exactly as provided. "
    "If nothing fits, respond with \"기타\" and explain why."
)

USER_PROMPT_TEMPLATE = """Classify the filing excerpt below.

Categories (choose exactly one):
[
  "증자", "자사주 매입/소각", "전환사채·신주인수권부사채", "대규모 공급·수주 계약",
  "소송/분쟁", "M&A/합병·분할", "지배구조·임원 변경", "감사 의견",
  "정기·수시 보고서", "증권신고서/투자설명서", "임원·주요주주 지분 변동",
  "정정 공시", "IR/설명회", "배당/주주환원", "기타"
]

If the category is "증자", add `"allocation": "주주배정"|"제3자배정"|"미확인"`.

Return JSON with:
{{
  "category": "...",  # one of the Korean labels above
  "allocation": "...",  # optional, only when category는 "증자"
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
