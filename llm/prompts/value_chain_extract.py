"""Prompt template for extracting value-chain relations."""

from __future__ import annotations

from textwrap import dedent
from typing import Dict, List


def get_prompt(ticker: str, context: str) -> List[Dict[str, str]]:
    instructions = dedent(
        f"""
        너는 금융 도메인의 관계 추출 전문가다. 아래 텍스트를 읽고 기업 간 관계를 JSON으로 추출하라.

        규칙:
        1. JSON 스키마는 다음과 같다.
        {{
          "suppliers": [{{"ticker": "...", "label": "..."}}],
          "customers": [{{"ticker": "...", "label": "..."}}],
          "competitors": [{{"ticker": "...", "label": "..."}}]
        }}
        2. ticker 를 모르면 빈 문자열로 두고 label 만 채운다.
        3. 동일 항목을 중복 추가하지 말고, 최대 5개까지만 나열한다.
        4. 텍스트에 근거가 없으면 해당 배열은 빈 배열로 둔다.
        5. 출력은 JSON 한 줄만 반환한다.

        대상 기업: {ticker}
        텍스트:
        {context.strip()}
        """
    ).strip()

    return [
        {
            "role": "system",
            "content": "너는 기업 밸류체인 관계를 정규화하는 분석가다. 지시를 따르고 JSON 한 줄만 출력하라.",
        },
        {
            "role": "user",
            "content": instructions,
        },
    ]


__all__ = ["get_prompt"]
