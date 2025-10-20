"""Prompt builder for table/footnote aware RAG answers."""

from __future__ import annotations

from typing import Any, Dict, List


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
    "You answer questions using tables, figures, and footnotes precisely. "
    "Quote table cells and page numbers explicitly. If data is missing, state it clearly."
)

USER_PROMPT_TEMPLATE = """Question:
{question}

Context:
{context_str}

Instructions:
- Provide a structured Korean answer referencing tables/figures/footnotes.
- Include citations such as (Table 2, p.5) or (Footnote 1, p.3).
- Summarise key numbers and add a \"Sources:\" list.
"""


def get_prompt(question: str, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    context_str = format_context_for_prompt(context_chunks)
    prompt = USER_PROMPT_TEMPLATE.format(question=question, context_str=context_str)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


__all__ = ["get_prompt", "format_context_for_prompt"]

