"""Minimal embedding helper shared by RAG and LightMem components."""

from __future__ import annotations

import os
from typing import Iterable, List, Sequence

import litellm

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def embed_text(text: str) -> List[float]:
    response = litellm.embedding(model=EMBEDDING_MODEL, input=[text])
    return response.data[0]["embedding"]


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    if not texts:
        return []
    response = litellm.embedding(model=EMBEDDING_MODEL, input=list(texts))
    return [item["embedding"] for item in response.data]

