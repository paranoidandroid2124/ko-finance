"""Thin wrapper around optional encryption helpers used for memory payloads.

We rely on AES/Fernet when the ``cryptography`` package is available.  In local
development or test environments the dependency may be missing; in that case we
fall back to a reversible no-op codec (base64).  This keeps the codepath simple
while allowing us to upgrade the security posture later without touching the
callers.
"""

from __future__ import annotations

import base64
from typing import Optional

from core.logging import get_logger
from core.env import env_str

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


_KEY = env_str("LIGHTMEM_ENCRYPTION_KEY")
if Fernet and _KEY:
    try:
        _CIPHER: Optional[Fernet] = Fernet(_KEY.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - malformed key
        logger.warning("Invalid LIGHTMEM_ENCRYPTION_KEY: %s. Falling back to base64-only mode.", exc)
        _CIPHER = None
else:
    _CIPHER = None


def encrypt(payload: bytes) -> bytes:
    if not payload:
        return payload
    if _CIPHER is None:
        return base64.urlsafe_b64encode(payload)
    return _CIPHER.encrypt(payload)


def decrypt(payload: bytes) -> bytes:
    if not payload:
        return payload
    if _CIPHER is None:
        try:
            return base64.urlsafe_b64decode(payload)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to base64-decode payload; returning original value.")
            return payload
    try:
        return _CIPHER.decrypt(payload)
    except InvalidToken:  # pragma: no cover - corrupted payload
        logger.warning("Unable to decrypt payload with configured key; returning raw bytes.")
        return payload

