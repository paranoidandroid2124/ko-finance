"""Shared helpers for FastAPI routers and other web modules."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status


def parse_uuid(
    value: Optional[str],
    *,
    detail: str = "잘못된 UUID 형식입니다.",
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Optional[uuid.UUID]:
    """Parse a UUID string used in web requests.

    Args:
        value: Raw UUID string or ``None``.
        detail: Error message when the value cannot be parsed.
        status_code: HTTP status code for the raised :class:`HTTPException`.

    Returns:
        Parsed :class:`uuid.UUID` or ``None`` when ``value`` is falsy.
    """

    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status_code, detail=detail) from exc


__all__ = ["parse_uuid"]
