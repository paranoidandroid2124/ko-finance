"""Lightweight sensory-layer helpers used to trim prompts before they reach the LLM.

This module does **not** call an external model yet — it provides a deterministic
placeholder that removes obvious boilerplate (extra whitespace, leading greetings)
and keeps the payload under a configurable character budget.  The idea is to offer
an integration point where later we can swap in a true prompt compressor
(e.g. llmlingua-2 or a LiteLLM call) without touching the downstream memory code.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

from core.logging import get_logger
from core.env import env_int

logger = get_logger(__name__)

_DEFAULT_MAX_CHARS = env_int("LIGHTMEM_SENSORY_MAX_CHARS", 1500, minimum=200)
_GREETING_RE = re.compile(r"^(?:안녕하세요|안녕|hello|hi|hey|您好)[!,. ]*", re.IGNORECASE)


@dataclass(frozen=True)
class PreprocessedPrompt:
    """Result returned by :func:`compress_prompt`.

    Attributes
    ----------
    original_length:
        Length of the original prompt string.
    compressed_length:
        Length after lightweight compression.
    text:
        The compressed prompt contents to feed into the STM/LTM pipeline.
    was_truncated:
        Indicates whether the payload exceeded ``max_chars`` and had to be cut.
    """

    original_length: int
    compressed_length: int
    text: str
    was_truncated: bool


def _normalise_whitespace(value: str) -> str:
    """Collapse consecutive whitespace and strip leading/trailing space."""

    collapsed = re.sub(r"\s+", " ", value)
    return collapsed.strip()


def _strip_leading_greetings(value: str) -> str:
    """Remove very common greeting phrases at the start of the message."""

    return _GREETING_RE.sub("", value, count=1)


def compress_prompt(text: str, max_chars: Optional[int] = None) -> PreprocessedPrompt:
    """Apply a deterministic sensory-layer compression pass.

    Parameters
    ----------
    text:
        The raw prompt provided by the caller.
    max_chars:
        Optional soft limit for the output length. When omitted the value is
        pulled from the ``LIGHTMEM_SENSORY_MAX_CHARS`` environment variable
        (default 1,500 characters).

    Notes
    -----
    The implementation intentionally stays simple so it can run in every
    environment (tests, local development) without additional dependencies.
    The function logs whenever truncation happens so we can later verify the
    compression ratios and decide when to integrate a model-driven approach.
    """

    baseline = text or ""
    cleaned = _strip_leading_greetings(baseline)
    cleaned = _normalise_whitespace(cleaned)

    limit = max_chars or _DEFAULT_MAX_CHARS
    if len(cleaned) > limit:
        logger.debug("Sensory compression truncated prompt from %d to %d chars.", len(cleaned), limit)
        truncated = cleaned[:limit].rsplit(" ", 1)[0] or cleaned[:limit]
        cleaned = truncated
        was_truncated = True
    else:
        was_truncated = False

    return PreprocessedPrompt(
        original_length=len(baseline),
        compressed_length=len(cleaned),
        text=cleaned,
        was_truncated=was_truncated,
    )

