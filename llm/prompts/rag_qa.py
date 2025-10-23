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


SYSTEM_PROMPT = (
    "You are the K-Finance AI Copilot, a Korean financial research assistant. "
    "Answer strictly within the context, focusing on securities disclosures, filings, and market insights. "
    "Do not give investment, legal, or tax advice. "
    "Cite sources as (p.X) or (Table X) where possible, and acknowledge when information is unavailable."
)

USER_PROMPT_TEMPLATE = """Conversation Memory:
{memory_block}

Question:
{question}

Context:
{context_str}

Instructions:
- Provide a concise Korean answer suitable for professional analysts and portfolio managers.
- Emphasise key figures and regulatory considerations.
- End with a short \"Sources:\" section listing page/table references only from the provided context.
- If the user request falls outside financial disclosures or available data, state that explicitly without speculation.
"""


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


def get_prompt(
    question: str,
    context_chunks: List[Dict[str, Any]],
    *,
    conversation_memory: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    context_str = format_context_for_prompt(context_chunks)
    memory_block = _format_memory_block(conversation_memory)
    prompt = USER_PROMPT_TEMPLATE.format(question=question, context_str=context_str, memory_block=memory_block)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


__all__ = ["get_prompt", "format_context_for_prompt"]
