"""Minimal embedding helper shared by RAG and LightMem components."""

from __future__ import annotations

import os
from typing import Iterable, List, Sequence, Any

import litellm

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def _clean_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def embed_text(text: str) -> List[float]:
    cleaned = _clean_text(text)
    if not cleaned:
        raise ValueError("text must be a non-empty string.")
    response = litellm.embedding(model=EMBEDDING_MODEL, input=[cleaned])
    return response.data[0]["embedding"]


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []
    cleaned_texts = [_clean_text(text) for text in texts]
    filtered = [text for text in cleaned_texts if text]
    if not filtered:
        return []
    response = litellm.embedding(model=EMBEDDING_MODEL, input=filtered)
    return [item["embedding"] for item in response.data]
