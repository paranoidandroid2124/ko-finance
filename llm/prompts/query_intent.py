"""Prompt template for classifying incoming user queries before running RAG."""

from __future__ import annotations

from typing import Dict, List

SYSTEM_PROMPT = (
    "너는 금융 도메인 어시스턴트의 전처리 필터이다. 사용자의 질문을 읽고 "
    "다음 셋 중 하나로 분류하라: "
    '"pass"(공시/뉴스 기반 정보가 필요), '
    '"semi_pass"(규제상 문제는 없으나 일반 잡담/자기소개/서비스 범위 외 요청), '
    '"block"(규제 또는 안전상 차단). '
    "JSON 한 줄만 출력해야 한다."
)

GUIDELINES = """
판정 기준:
- pass: 금융 공시, 기업 재무, 주주 구성, 시장 이슈 등 분석이 필요한 질문.
- semi_pass: 서비스 소개 요청, 안부/인사/자기소개, 잡담, 기술 지원, 범위 외 일반 상식 질문.
- block: 투자 권유/매수매도 요구, 개인정보/민감 데이터 요청, 규제 또는 안전 위반 가능성.

결과 형식:
{"decision": "pass|semi_pass|block", "reason": "한국어 한 줄 설명"}
"""


def get_prompt(question: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": GUIDELINES.strip()},
        {
            "role": "user",
            "content": (
                "다음 사용자의 질문을 분류하십시오.\n"
                f"질문: {question}\n\n"
                'JSON 형식: {"decision": "...", "reason": "..."}'
            ),
        },
    ]


__all__ = ["get_prompt"]

