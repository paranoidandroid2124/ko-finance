"""Prompt template for fact self-check."""

from __future__ import annotations

SYSTEM_PROMPT = (
    "You verify whether extracted facts are supported by the filing excerpt. "
    "Return JSON only. Adjust or drop unsupported facts."
)

USER_PROMPT_TEMPLATE = """Given the filing excerpt and candidate facts, validate support.

Return JSON:
{{
  "supported": true|false,
  "faithfulness_score": 0.0-1.0,
  "unsupported_fields": ["..."],
  "corrected_json": {{
      "facts": [ ... normalized fact objects ... ]
  }},
  "notes": "optional observations"
}}

[FILING EXCERPT]
{{FILING_MD_SNIPPET}}

[CANDIDATE FACTS]
{{CANDIDATE_JSON}}
"""

__all__ = ["SYSTEM_PROMPT", "USER_PROMPT_TEMPLATE"]

