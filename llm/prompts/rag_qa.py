"""Prompt builder for standard RAG answers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_context_for_prompt(context_chunks: List[Dict[str, Any]]) -> str:
    """Format context chunks into a readable string."""
    parts: List[str] = []
    for index, chunk in enumerate(context_chunks, start=1):
        chunk_type = (chunk.get("type") or "text").lower()
        page = chunk.get("page_number")
        header = f"--- Context {index} (type={chunk_type}"
        if page is not None:
            header += f", page={page}"
        header += ") ---"
        content = chunk.get("content") or ""
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


SYSTEM_PROMPT_STRICT = (
    "당신은 K-Finance AI Copilot이며, 한국어로 금융 공시와 시장 데이터를 분석하는 리서치 어시스턴트입니다. "
    "제공된 공시·보고서·시장 데이터 범위 내에서만 답변하고, 투자·법률·세무 자문은 절대 제공하지 마세요. "
    "항상 전문적인 어조를 유지하면서, 출처는 기업명·문서명·페이지처럼 사람이 이해하기 쉬운 한국어 레이블로 제시하세요."
)

SYSTEM_PROMPT_FLEX = (
    "당신은 K-Finance AI Copilot입니다. 제공된 컨텍스트를 우선 활용해 금융 관련 질문에 대해 정제된 한국어 답변을 작성하세요. "
    "명확성을 높이기 위해 널리 알려진 금융 배경지식이나 정의를 보충할 수 있으나, 반드시 '(일반 지식)'으로 표시하고 컨텍스트 내용과 구분하세요. "
    "출처는 페이지·표 번호 등 세부 정보를 포함하되 사용자가 즉시 이해할 수 있는 한국어 설명형 레이블로 정리하세요. "
    "항상 전문적인 어조를 유지하고, 투자·법률·세무 자문은 금지입니다."
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
