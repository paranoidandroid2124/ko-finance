"""Prompt builder for table/footnote aware RAG answers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_context_for_prompt(context_chunks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for index, chunk in enumerate(context_chunks, start=1):
        chunk_type = (chunk.get("type") or "text").lower()
        page = chunk.get("page_number")
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        doc_label = chunk.get("doc_label") or metadata.get("doc_label")
        doc_title = chunk.get("title") or metadata.get("doc_title")
        meta = []
        if page is not None:
            meta.append(f"page={page}")
        section = chunk.get("section")
        if section:
            meta.append(f"section={section}")
        header_bits = []
        if doc_label and doc_title:
            header_bits.append(f"{doc_label}: {doc_title}")
        elif doc_label:
            header_bits.append(str(doc_label))
        header_bits.append(f"type={chunk_type}")
        if meta:
            header_bits.extend(meta)
        header = f"--- Context {index} ({', '.join(header_bits)}) ---"
        content = chunk.get("content") or ""
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


SYSTEM_PROMPT_STRICT = (
    "당신은 Nuvien AI Copilot이며, 표와 각주를 중심으로 한 공시 정보를 한국어로 정리하는 어시스턴트입니다. "
    "제공된 금융 문서 범위 내에서만 답변하고, 투자·법률·세무 자문은 하지 마세요. "
    "항상 전문적인 어조를 유지하면서, 표·각주 출처는 기업명·섹션명·페이지 등 사용자가 이해하기 쉬운 한국어 레이블로 제시하세요."
)

SYSTEM_PROMPT_FLEX = (
    "당신은 Nuvien AI Copilot입니다. 제공된 컨텍스트를 우선 활용해 표와 각주, 주요 수치를 강조한 구조화된 한국어 답변을 작성하세요. "
    "이해를 돕기 위해 널리 알려진 금융 배경지식이나 정의를 보충할 수 있으나, 해당 문장에 '(일반 지식)'을 붙여 컨텍스트 기반 정보와 구분하세요. "
    "표·각주 출처는 페이지·표 번호 등 세부 정보를 포함하되 사용자가 즉시 이해할 수 있는 한국어 설명형 레이블로 정리하세요. "
    "항상 전문적인 어조를 유지하고 투자·법률·세무 자문은 금지입니다."
)

INSTRUCTIONS_STRICT = (
    "- 컨텍스트에 포함된 표·그림·각주를 참조하며 구조화된 한국어 답변을 작성하세요.\n"
    "- 표·각주를 언급할 때는 \"○○표: 내용 (p.X)\"처럼 한국어 설명과 페이지 정보를 함께 적으세요.\n"
    "- 핵심 수치를 요약하고 응답 끝에 \"출처:\" 줄을 추가하되, 각 항목을 사용자 친화적인 문장으로 정리하세요.\n"
    "- 정보가 없으면 추측하지 말고 명확히 없다고 밝히세요."
)

INSTRUCTIONS_FLEX = (
    "- 표와 각주에 담긴 핵심 정보를 한국어로 정리하되, \"Table:4\" 등의 태그는 \"표 4: 배당금 내역 (p.4)\"처럼 자연스러운 설명으로 바꾸세요.\n"
    "- 널리 알려진 금융 배경지식이 도움이 되면 간단히 보충하고 해당 문장에 \"(일반 지식)\"을 붙여 구분하세요.\n"
    "- 응답은 구조화된 형식을 유지하고 끝에 관련 표·그림·각주 정보를 요약한 \"출처:\" 줄을 제공하세요.\n"
    "- 컨텍스트에 정보가 없으면 명확히 없다고 알리고 추측하지 마세요."
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
        parts.append("- 참고 문헌: " + ", ".join(str(item) for item in citations))
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
