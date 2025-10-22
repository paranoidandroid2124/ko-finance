"""Prompt for pre-judging user questions against regulatory guardrails."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "당신은 금융 규제 준수 검사관입니다. 사용자가 입력한 질문만을 검토하여 "
    "한국 자본시장법·금융소비자보호법 등에서 금지하는 투자 권유/과장 표현 여부를 사전 판정합니다. "
    "반드시 JSON 형식으로만 응답하세요: {\"decision\": \"pass|block\", \"reason\": \"간단한 한국어 설명\"}."
)

EVALUATION_GUIDELINES = (
    "다음 금지 항목을 모두 검토하세요:\n"
    "1. 특정 종목·가격·기간이 명시된 매수/매도/목표가/손절가 요청 또는 권유 요구\n"
    "2. 확정 수익·원금보장 등을 기대하며 구체적 조언을 요구하는 표현\n"
    "3. DM·1:1 상담·개별 투자 조언을 유도하는 문구\n"
    "4. 허위 사실이나 검증되지 않은 루머에 기반한 투자 판단을 요구하는 표현\n"
    "위 조건 중 하나라도 충족하면 decision을 'block' 으로, 그 외에는 'pass' 로 응답하세요."
)


def get_prompt(question: str) -> List[Dict[str, str]]:
    user_content = (
        "다음은 사용자의 질문입니다. 규제 위반 여부를 판단하세요.\n"
        f"질문: {question}\n\n"
        "JSON 형식: {\"decision\": \"pass 또는 block\", \"reason\": \"한국어 한 줄 설명\"}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": EVALUATION_GUIDELINES},
        {"role": "user", "content": user_content},
    ]
