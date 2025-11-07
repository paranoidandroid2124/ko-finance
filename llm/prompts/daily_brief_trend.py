"""Prompt template for generating the daily brief headline and overview."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "You are an analyst preparing a Korean daily market briefing. "
    "Write concise, informative copy that highlights changes from the previous day. "
    "Respond with JSON only."
)

USER_PROMPT_TEMPLATE = """다음 일일 지표를 기반으로 브리핑 헤드라인과 한 문장 요약을 작성하세요.

- 헤드라인은 60자 이내의 간결한 한국어 문장으로 작성합니다.
- 요약은 120자 이내에서 핵심 변화(증가·감소, 주요 토픽, 알림 현황)를 자연스럽게 설명합니다.
- 데이터가 부족하거나 변화가 미미하면 그 사실을 명시합니다.

DATA:
{{CONTEXT_JSON}}

JSON 응답 형식:
{{
  "headline": "...",
  "summary": "..."
}}
"""


def get_prompt(context_json: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.replace("{{CONTEXT_JSON}}", context_json)},
    ]


__all__ = ["get_prompt"]

