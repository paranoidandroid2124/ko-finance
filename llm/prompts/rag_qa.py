"""Prompt builder for standard RAG answers."""

from __future__ import annotations

from typing import Any, Dict, List


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
    "You answer questions using only the provided context. "
    "Cite sources as (p.X) or (Table X) where possible. "
    "If the answer is unknown, say so."
)

USER_PROMPT_TEMPLATE = """Question:
{question}

Context:
{context_str}

Instructions:
- Provide a concise Korean answer suitable for professional investors.
- Highlight key figures.
- End with a short \"Sources:\" section listing page/table references.
"""


def get_prompt(question: str, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    context_str = format_context_for_prompt(context_chunks)
    prompt = USER_PROMPT_TEMPLATE.format(question=question, context_str=context_str)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]


__all__ = ["get_prompt", "format_context_for_prompt"]

