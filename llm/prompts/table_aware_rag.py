"""Prompt builder for table/footnote aware RAG answers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def format_context_for_prompt(context_chunks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for index, chunk in enumerate(context_chunks, start=1):
        chunk_type = (chunk.get("type") or "text").lower()
        page = chunk.get("page_number")
        meta = []
        if page is not None:
            meta.append(f"page={page}")
        section = chunk.get("section")
        if section:
            meta.append(f"section={section}")
        header = f"--- Context {index} (type={chunk_type}"
        if meta:
            header += ", " + ", ".join(meta)
        header += ") ---"
        content = chunk.get("content") or ""
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


SYSTEM_PROMPT = (
    "You are the K-Finance AI Copilot specialising in tabular and footnote disclosures. "
    "Stay within the provided financial documents, cite specific tables/figures with page numbers, "
    "and never offer investment, legal, or tax advice."
)

USER_PROMPT_TEMPLATE = """Conversation Memory:
{memory_block}

Question:
{question}

Context:
{context_str}

Instructions:
- Provide a structured Korean answer referencing tables/figures/footnotes.
- Include citations such as (Table 2, p.5) or (Footnote 1, p.3).
- Summarise key numbers and add a \"Sources:\" list.
- If information is unavailable, state it clearly without speculation.
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
        parts.append("- 참고 문헌: " + ", ".join(str(item) for item in citations))
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
