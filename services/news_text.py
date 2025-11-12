"""Reusable helpers for cleaning news-related text fields."""

from __future__ import annotations

import html
import re
from typing import Optional

_TAG_PATTERN = re.compile(r"<[^>]+>")
_BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)
_INLINE_WHITESPACE_PATTERN = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")


def sanitize_news_summary(value: Optional[str], *, max_chars: Optional[int] = None) -> Optional[str]:
    """Normalize a news summary by stripping tags and collapsing whitespace.

    Args:
        value: Raw summary text (may include HTML tags or excessive whitespace).
        max_chars: Optional soft limit for the resulting summary. When provided,
            the function trims on word boundaries; if no boundary exists within
            the limit it falls back to a hard cutoff.

    Returns:
        Cleaned summary text or ``None`` when the input is empty after cleanup.
    """

    if value is None:
        return None

    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return None

    text = _BREAK_PATTERN.sub("\n", text)
    text = _TAG_PATTERN.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INLINE_WHITESPACE_PATTERN.sub(" ", text)
    text = _MULTI_NEWLINE_PATTERN.sub("\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    if not text:
        return None

    if max_chars is None:
        return text

    max_chars = max_chars if max_chars >= 0 else 0
    if max_chars == 0 or len(text) <= max_chars:
        return text

    clipped = text[:max_chars]
    boundary = max(clipped.rfind(" "), clipped.rfind("\n"))
    if boundary != -1:
        clipped = clipped[:boundary]
    clipped = clipped.rstrip()
    return clipped or text[:max_chars].rstrip()


__all__ = ["sanitize_news_summary"]
