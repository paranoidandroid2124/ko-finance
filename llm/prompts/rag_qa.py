"""Prompt builder for standard RAG answers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_context_for_prompt(context_chunks: List[Dict[str, Any]]) -> str:
    """Format context chunks into a readable string."""
    parts: List[str] = []
    for index, chunk in enumerate(context_chunks, start=1):
        chunk_type = (chunk.get("type") or "text").lower()
        page = chunk.get("page_number")
        source_url = (
            chunk.get("viewer_url")
            or chunk.get("document_url")
            or chunk.get("download_url")
            or chunk.get("source_url")
        )
        header = f"--- Context {index} (type={chunk_type}"
        if page is not None:
            header += f", page={page}"
        header += ") ---"
        content = chunk.get("content") or ""
        if source_url:
            parts.append(f"{header}\nSource: {source_url}\n{content}")
        else:
            parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


SYSTEM_PROMPT_STRICT = (
    "당신은 Nuvien AI Copilot이며, 한국어로 금융 공시와 시장 데이터를 분석하는 리서치 어시스턴트입니다. "
    "제공된 공시·보고서·시장 데이터 범위 내에서만 답변하고, 투자·법률·세무 자문은 절대 제공하지 마세요. "
    "항상 전문적인 어조를 유지하면서, 출처는 기업명·문서명·페이지처럼 사람이 이해하기 쉬운 한국어 레이블로 제시하세요. "
    "[Nuvien Focus Score 해석 가이드] derived_metrics.focus_score가 있으면 총점(total_score)과 서브점수(Impact/Clarity/Consistency/Confirmation)를 그대로 요약하고, 없으면 점수 생성/추정 금지. "
    "서브 지표 의미: Impact(시장 반응 강도), Clarity(정보 명확성), Consistency(과거 일관성), Confirmation(외부 교차 검증). "
    "점수 나열을 넘어서 패턴을 해석하라. 예시: Impact↑ & Consistency↓ → 강한 반응이나 재현성 낮음(단기 투기성 가능). Clarity↓ & Impact↑ → 시장 반응은 뜨겁지만 정보가 불충분(원문 확인 요청). Confirmation↑ & Impact↓ → 뉴스는 뜨거우나 시장 반응은 미미(괴리 존재). "
    "[법적 준수/안전 화법] 투자 조언·매수/매도 추천·미래 주가 예측·가치 평가(저평가/고평가) 표현을 금지하고, 관찰된 패턴만 객관적으로 기술하라. "
    "가능성·추측 표현을 피하고 '과거 데이터에 따르면 ~한 경향'처럼 서술하라. '리스크/기회/경고' 대신 '괴리 관찰', '추가 확인 권장' 등 중립 표현을 사용하고, 최종 판단 책임은 사용자에게 있음을 암시적으로 포함하라. "
    "브리핑/하이라이트를 생성할 때도 위 Focus Score 해석과 안전 화법을 동일하게 적용하라."
)

SYSTEM_PROMPT_FLEX = (
    "당신은 Nuvien AI Copilot입니다. 제공된 컨텍스트를 우선 활용해 금융 관련 질문에 대해 정제된 한국어 답변을 작성하세요. "
    "명확성을 높이기 위해 널리 알려진 금융 배경지식이나 정의를 보충할 수 있으나, 반드시 '(일반 지식)'으로 표시하고 컨텍스트 내용과 구분하세요. "
    "출처는 페이지·표 번호 등 세부 정보를 포함하되 사용자가 즉시 이해할 수 있는 한국어 설명형 레이블로 정리하세요. "
    "항상 전문적인 어조를 유지하고, 투자·법률·세무 자문은 금지입니다. "
    "[Nuvien Focus Score 해석 가이드] derived_metrics.focus_score가 있으면 총점(total_score)과 서브점수(Impact/Clarity/Consistency/Confirmation)를 그대로 요약하고, 없으면 점수 생성/추정 금지. "
    "서브 지표 의미: Impact(시장 반응 강도), Clarity(정보 명확성), Consistency(과거 일관성), Confirmation(외부 교차 검증). "
    "점수 나열을 넘어서 패턴을 해석하라. 예시: Impact↑ & Consistency↓ → 강한 반응이나 재현성 낮음(단기 투기성 가능). Clarity↓ & Impact↑ → 시장 반응은 뜨겁지만 정보가 불충분(원문 확인 요청). Confirmation↑ & Impact↓ → 뉴스는 뜨거우나 시장 반응은 미미(괴리 존재). "
    "[법적 준수/안전 화법] 투자 조언·매수/매도 추천·미래 주가 예측·가치 평가(저평가/고평가) 표현을 금지하고, 관찰된 패턴만 객관적으로 기술하라. "
    "가능성·추측 표현을 피하고 '과거 데이터에 따르면 ~한 경향'처럼 서술하라. '리스크/기회/경고' 대신 '괴리 관찰', '추가 확인 권장' 등 중립 표현을 사용하고, 최종 판단 책임은 사용자에게 있음을 암시적으로 포함하라. "
    "브리핑/하이라이트를 생성할 때도 위 Focus Score 해석과 안전 화법을 동일하게 적용하라."
)

INSTRUCTIONS_STRICT = (
    "- 전문 애널리스트를 대상으로 간결한 한국어로 답변하세요.\n"
    "- 컨텍스트에서 확인되는 핵심 수치와 규제 사항을 강조하세요.\n"
    "- 응답 마지막에 \"출처:\" 줄을 추가하되, 각 항목을 \"기업명·문서 제목 (p.X)\"처럼 한국어 설명과 페이지 정보를 함께 적으세요.\n"
    "- 컨텍스트에 정보가 없으면 추측하지 말고 명확히 부재를 알리세요."
)

INSTRUCTIONS_FLEX = (
    "- 제공된 컨텍스트를 우선으로 삼아 정제된 한국어 요약을 작성하세요.\n"
    "- \"Source: 1\", \"Table:4\" 같은 태그는 \"삼성전자 배당 공시 (p.4)\", \"표 4: 배당금 내역\"처럼 자연스러운 한국어 설명으로 바꾸세요.\n"
    "- 널리 알려진 금융 배경지식이나 정의가 도움이 되면 짧게 보충하되 해당 문장 끝에 \"(일반 지식)\"을 붙여 컨텍스트 내용과 구분하세요.\n"
    "- 응답 마지막에 관련 페이지/표 번호만 담은 \"출처:\" 줄을 추가하고, 각 항목을 사람이 즉시 이해할 수 있는 설명형 문장으로 작성하세요."
)

_SYSTEM_PROMPTS = {
    "strict": SYSTEM_PROMPT_STRICT,
    "flex": SYSTEM_PROMPT_FLEX,
}

_INSTRUCTION_MAP = {
    "strict": INSTRUCTIONS_STRICT,
    "flex": INSTRUCTIONS_FLEX,
}


def _format_memory_block(memory: Optional[Dict[str, Any]]) -> str:
    if not memory:
        return "요약 정보가 없습니다."
    parts: List[str] = []
    summary = (memory.get("summary") or "").strip()
    if summary:
        parts.append(f"- 요약: {summary}")
    recent_turns = memory.get("recent_turns") or []
    if recent_turns:
        formatted_turns: List[str] = []
        for turn in recent_turns:
            role = str(turn.get("role") or "").strip().lower()
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            role_label = "사용자" if role == "user" else "Copilot"
            formatted_turns.append(f"{role_label}: {content}")
        if formatted_turns:
            parts.append("- 최근 대화:\n  " + "\n  ".join(formatted_turns))
    citations = memory.get("citations") or []
    if citations:
        citation_line = ", ".join(str(item) for item in citations)
        parts.append(f"- 참고 문헌: {citation_line}")
    return "\n".join(parts) if parts else "요약 정보가 없습니다."


def _format_meta_block(meta: Optional[Dict[str, Any]]) -> str:
    if not meta:
        return ""
    lines: List[str] = []
    current_date = meta.get("current_date_local")
    if current_date:
        lines.append(f"- 오늘 날짜: {current_date}")
    current_time_local = meta.get("current_datetime_local")
    if current_time_local:
        lines.append(f"- 현재 시각(KST): {current_time_local}")
    current_time_utc = meta.get("current_datetime_utc")
    if current_time_utc:
        lines.append(f"- 현재 시각(UTC): {current_time_utc}")
    range_meta = meta.get("relative_date_range")
    if isinstance(range_meta, dict):
        display = range_meta.get("label_display") or range_meta.get("label")
        start_local = range_meta.get("start_local")
        end_local = range_meta.get("end_local")
        if start_local and end_local:
            lines.append(f"- 요청된 기간: {display} ({start_local} ~ {end_local})")
        else:
            lines.append(f"- 요청된 기간: {display}")
    tool_context = meta.get("tool_context")
    if isinstance(tool_context, str):
        stripped = tool_context.strip()
        if stripped:
            lines.append(f"- 현재 툴 컨텍스트:\n{stripped}")
    return "\n".join(lines)


def get_prompt(
    question: str,
    context_chunks: List[Dict[str, Any]],
    *,
    conversation_memory: Optional[Dict[str, Any]] = None,
    mode: str = "strict",
    meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    context_str = format_context_for_prompt(context_chunks)
    memory_block = _format_memory_block(conversation_memory)
    normalized_mode = mode if mode in _SYSTEM_PROMPTS else "strict"
    meta_block = _format_meta_block(meta)
    sections: List[str] = [
        f"대화 메모:\n{memory_block}",
        f"질문:\n{question}",
    ]
    if meta_block:
        sections.append(f"메타 정보:\n{meta_block}")
    sections.append(f"컨텍스트:\n{context_str}")
    sections.append(f"지시 사항:\n{_INSTRUCTION_MAP[normalized_mode]}")
    prompt = "\n\n".join(sections)
    return [
        {"role": "system", "content": _SYSTEM_PROMPTS[normalized_mode]},
        {"role": "user", "content": prompt},
    ]


__all__ = ["get_prompt", "format_context_for_prompt"]
