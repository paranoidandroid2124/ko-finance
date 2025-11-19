"""Prompt template for SemanticRouter decisions."""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Dict, List

from schemas.router import RouteDecision

ROUTE_SCHEMA_JSON = json.dumps(
    RouteDecision.model_json_schema(),
    ensure_ascii=False,
    indent=2,
)

ACTION_GUIDANCE = dedent(
    """
    허용된 action 값:
    - RAG_ANSWER: 일반적인 재무/기업 분석 답변이 필요할 때 사용.
    - TOOL_NEWS: 최신 뉴스/속보/공시 패널을 열어야 할 때 사용.
    - TOOL_DISCLOSURE: 특정 공시 원문을 열람하거나 공시 리스트를 보여줄 때 사용.
    - TOOL_EVENT_STUDY: 과거 이벤트(실적발표, 유상증자 등) 전후 주가 패턴을 분석할 때 사용.
    - TOOL_MARKET_BRIEF: ‘한눈에 보기’ 스타일의 마켓 브리핑을 보여줄 때 사용.
    - CLARIFY: action 후보가 2개 이상으로 모호하고 추가 입력이 필요할 때 사용.
    - BLOCK_COMPLIANCE: 투자 자문, 매수/매도 권유 등 규제 키워드가 포함될 때 사용.

    규칙:
    1. action 은 위 목록 중 하나여야 한다.
    2. confidence 는 0~1 사이의 소수로, 2 decimal precision 정도로 출력한다.
    3. tickers 는 대문자, 하이픈 없는 종목 코드 목록으로 deduplicate 해서 채운다.
    4. parameters 는 선택된 action 을 실행하는 데 필요한 argument 를 key-value 로 채운다.
       예) 이벤트 스터디: {"ticker": "NVDA", "event_type": "earnings", "window_days": 30}
    5. CLARIFY 일 때는 suggestions 배열에 2~3개의 대안을 넣고, 각 항목은 action/label/parameters 를 포함한다.
    6. BLOCK_COMPLIANCE 일 때는 blocked_phrases 에 검출된 위험 키워드를 모두 넣는다.
    7. JSON schema 를 반드시 준수하고, JSON 한 줄만 출력한다.
    """
).strip()


def get_prompt(question: str) -> List[Dict[str, str]]:
    """Build the chat prompt for the semantic router."""

    user_instructions = dedent(
        f"""
        사용자가 보낸 한국어 질의에 대해 가장 적절한 action 을 선택하세요.
        JSON schema:
        {ROUTE_SCHEMA_JSON}

        {ACTION_GUIDANCE}

        질의:
        {question.strip()}
        """
    ).strip()

    return [
        {"role": "system", "content": "너는 K-Finance Copilot 의 라우팅 엔진이다. 설명 없이 JSON 만 출력한다."},
        {"role": "assistant", "content": ACTION_GUIDANCE},
        {"role": "user", "content": user_instructions},
    ]


__all__ = ["get_prompt"]

