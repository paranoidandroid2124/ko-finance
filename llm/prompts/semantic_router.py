"""Prompt template for SemanticRouter decisions."""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Dict, List

from schemas.router import RouteDecision
from services.tool_registry import list_tools

ROUTE_SCHEMA_JSON = json.dumps(
    RouteDecision.model_json_schema(),
    ensure_ascii=False,
    indent=2,
)

_TOOL_GUIDANCE_LINES: List[str] = []
for tool in list_tools():
    descriptor = (
        f"- {tool.tool_id}: call_name='{tool.call_name}', intent='{tool.intent}', "
        f"ui={tool.ui_container.value}, paywall={tool.paywall.value}. {tool.description}"
    )
    _TOOL_GUIDANCE_LINES.append(descriptor)

TOOL_GUIDANCE = "\n".join(_TOOL_GUIDANCE_LINES)

ROUTER_RULES = dedent(
    """
    필드 규칙:
    1. intent 는 commander tool intent (예: event_study, disclosure_lookup) 로 registry 표와 일치해야 함.
    2. tool_call.name 은 registry 의 call_name 중 하나. arguments 는 필요한 파라미터만 포함.
    3. ui_container 와 paywall 값은 registry 와 동일해야 함.
    4. requires_context 는 도구 실행 전에 필요한 LightMem/tenant context 를 모두 채움.
    5. safety.block 이 true 이면 응답을 차단하고 reason 에 사유를 설명, keywords 에 감지된 문구를 넣음.
    6. tickers 는 질의에 등장한 종목 코드를 대문자/공백 제거 후 deduplicate 해서 채움.
    7. reason 은 선택 근거를 한국어로 1~2문장 작성.
    8. confidence 는 0~1 범위 실수 (소수점 둘째 자리 권장).
    9. JSON schema 를 엄격히 준수하고, JSON 한 줄만 출력.

    규제:
    - "매수", "매도", "사라", "팔라", "추천", "목표가" 등 투자자문 표현이 있으면 tool_call.name="compliance.block" 으로 설정하고 safety.block=true.
    - 단순 소통/스몰톡이면 rag.answer 사용.

    라우팅 힌트:
    - "왜 떨어졌어", "최근 뉴스 없어?", "악재/호재 있나" 처럼 리스크/이슈를 묻는 질문은 news.rag 를 선택하고 arguments 에 query 와 ticker 를 넣는다.
    - "다 같이 빠지나?", "경쟁사랑 비교해 줘", "섹터 문제야?" 등 상대 비교 질문은 peer.compare 를 선택하고 ticker 와 기간(period_days)을 지정한다.

    - 특정 이벤트 이후 주가 영향을 묻는 질문은 event_study.query 를 선택하고 arguments 에 ticker, event_date(YYYY-MM-DD), window(정수, 기본 5)를 포함한다.

    Commander Tool Reference:
    {tool_reference}
    """
).strip().format(tool_reference=TOOL_GUIDANCE)


def get_prompt(question: str) -> List[Dict[str, str]]:
    """Build the chat prompt for the semantic router."""

    user_instructions = dedent(
        f"""
        사용자의 한국어 질의를 분석하여 commander tool 을 결정하세요.
        JSON schema:
        {ROUTE_SCHEMA_JSON}

        {ROUTER_RULES}

        질의:
        {question.strip()}
        """
    ).strip()

    return [
        {"role": "system", "content": "너는 Nuvien Copilot 의 라우팅 엔진이다. 설명 없이 JSON 만 출력한다."},
        {"role": "assistant", "content": ROUTER_RULES},
        {"role": "user", "content": user_instructions},
    ]


__all__ = ["get_prompt"]
