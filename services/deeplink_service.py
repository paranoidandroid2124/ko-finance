"""Helpers for issuing and resolving signed RAG deeplink tokens."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt

from core.env import env_int, env_str

logger = logging.getLogger(__name__)

DEEPLINK_SECRET = env_str("DEEPLINK_SECRET", "").strip()
DEEPLINK_TTL_SECONDS = env_int("DEEPLINK_TTL_SECONDS", 900, minimum=60)
DEEPLINK_VIEWER_BASE_URL = (env_str("DEEPLINK_VIEWER_BASE_URL", "/viewer") or "/viewer").strip()
DEEPLINK_AUDIENCE = "rag.deeplink"
DEEPLINK_ALGORITHM = "HS256"


class DeeplinkError(Exception):
    """Base error raised when deeplinks cannot be issued or resolved."""

    code = "deeplink_error"

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class DeeplinkDisabledError(DeeplinkError):
    code = "deeplink_disabled"


class DeeplinkInvalidError(DeeplinkError):
    code = "deeplink_invalid"


class DeeplinkExpiredError(DeeplinkError):
    code = "deeplink_expired"


def is_enabled() -> bool:
    """Return True when deeplink signing is configured."""

    return bool(DEEPLINK_SECRET and DEEPLINK_TTL_SECONDS > 0)


def _normalize_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def issue_token(
    *,
    document_url: str,
    page_number: int,
    char_start: Optional[int] = None,
    char_end: Optional[int] = None,
    sentence_hash: Optional[str] = None,
    chunk_id: Optional[str] = None,
    document_id: Optional[str] = None,
    excerpt: Optional[str] = None,
) -> str:
    """Return a signed deeplink token for the provided citation metadata."""

    if not is_enabled():
        raise DeeplinkDisabledError("RAG deeplink signing is disabled.")

    if not document_url:
        raise DeeplinkInvalidError("Document URL is required for deeplink issuance.")

    page_value = _normalize_optional_int(page_number)
    if page_value is None or page_value <= 0:
        raise DeeplinkInvalidError("Page number must be a positive integer.")

    now = int(time.time())
    payload: Dict[str, Any] = {
        "aud": DEEPLINK_AUDIENCE,
        "iat": now,
        "exp": now + int(DEEPLINK_TTL_SECONDS),
        "document_url": document_url,
        "page_number": page_value,
    }
    optional_fields = {
        "char_start": _normalize_optional_int(char_start),
        "char_end": _normalize_optional_int(char_end),
        "sentence_hash": sentence_hash.strip() if isinstance(sentence_hash, str) else None,
        "chunk_id": chunk_id.strip() if isinstance(chunk_id, str) else None,
        "document_id": document_id.strip() if isinstance(document_id, str) else None,
    }
    if excerpt and isinstance(excerpt, str):
        trimmed = excerpt.strip()
        if trimmed:
            optional_fields["excerpt"] = trimmed[:2000]
    payload.update({key: value for key, value in optional_fields.items() if value is not None})

    token = jwt.encode(payload, DEEPLINK_SECRET, algorithm=DEEPLINK_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def build_viewer_url(token: str) -> str:
    """Return the viewer URL for the provided token."""

    base = DEEPLINK_VIEWER_BASE_URL or "/viewer"
    if "{token}" in base:
        return base.replace("{token}", token)
    if base.endswith("/"):
        return f"{base}{token}"
    return f"{base}/{token}"


def resolve_token(token: str) -> Dict[str, Any]:
    """Decode a deeplink token and return the payload for rendering."""

    if not is_enabled():
        raise DeeplinkDisabledError("RAG deeplink verification is disabled.")
    if not token:
        raise DeeplinkInvalidError("Deeplink token is required.")
    try:
        payload = jwt.decode(
            token,
            DEEPLINK_SECRET,
            algorithms=[DEEPLINK_ALGORITHM],
            audience=DEEPLINK_AUDIENCE,
        )
    except jwt.ExpiredSignatureError as exc:
        raise DeeplinkExpiredError("Deeplink token has expired.") from exc
    except jwt.InvalidTokenError as exc:  # pragma: no cover - upstream library ensures coverage
        raise DeeplinkInvalidError("Deeplink token is invalid.") from exc

    document_url = payload.get("document_url")
    page_number = _normalize_optional_int(payload.get("page_number"))
    if not document_url or page_number is None:
        raise DeeplinkInvalidError("Deeplink token is missing document metadata.")

    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
    response = {
        "token": token,
        "document_url": document_url,
        "page_number": page_number,
        "char_start": _normalize_optional_int(payload.get("char_start")),
        "char_end": _normalize_optional_int(payload.get("char_end")),
        "sentence_hash": payload.get("sentence_hash"),
        "chunk_id": payload.get("chunk_id"),
        "document_id": payload.get("document_id"),
        "excerpt": payload.get("excerpt"),
        "expires_at": expires_at,
    }
    return response


__all__ = [
    "DEEPLINK_VIEWER_BASE_URL",
    "DeeplinkDisabledError",
    "DeeplinkError",
    "DeeplinkExpiredError",
    "DeeplinkInvalidError",
    "build_viewer_url",
    "is_enabled",
    "issue_token",
    "resolve_token",
]
