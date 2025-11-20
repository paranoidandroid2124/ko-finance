"""Prompt template for summarising chat transcripts."""

from __future__ import annotations

from typing import List

SYSTEM_PROMPT = (
    "You are the Nuvien AI Copilot summarising prior Korean chat transcripts about financial disclosures. "
    "Write concise, factual Korean summaries that highlight what the user learned, key instruments, and any follow-up steps. "
    "Do not offer investment, legal, or tax advice."
)

USER_PROMPT_TEMPLATE = """다음은 사용자와 Nuvien Copilot 사이의 과거 대화 로그입니다.

{transcript}

지침:
- 핵심 질문과 Copilot의 답변을 2-3문장으로 요약합니다.
- 불필요한 감탄사, 과도한 수식은 제거합니다.
- 투자/법률/세무 자문 문구는 포함하지 않습니다.

요약을 간결한 한국어 문단 1개로 작성하세요."""


def get_prompt(transcript: str) -> List[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(transcript=transcript)},
    ]


__all__ = ["get_prompt"]

