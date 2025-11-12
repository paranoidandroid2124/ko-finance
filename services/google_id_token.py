"""Helpers for verifying Google Workspace ID tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from google.auth.transport import requests
from google.oauth2 import id_token

from core.env import env_str
from core.logging import get_logger

logger = get_logger(__name__)

_CLIENT_ID = env_str("GOOGLE_ADMIN_CLIENT_ID")
_ALLOWED_DOMAIN = env_str("GOOGLE_ADMIN_ALLOWED_DOMAIN")


@dataclass(frozen=True)
class GoogleIdTokenPayload:
    email: str
    subject: str
    picture: Optional[str]
    name: Optional[str]
    hosted_domain: Optional[str]


class GoogleIdTokenVerificationError(RuntimeError):
    """
    Raised when Google ID token verification fails or required env vars are missing.
    """

    def __init__(self, message: str, *, code: str = "google_sso.invalid_token"):
        super().__init__(message)
        self.code = code


def verify_admin_google_id_token(raw_token: str) -> GoogleIdTokenPayload:
    """
    Validate a Google ID token for Workspace admins.

    Returns a structured payload when successful; raises GoogleIdTokenVerificationError otherwise.
    """

    if not _CLIENT_ID:
        raise GoogleIdTokenVerificationError("GOOGLE_ADMIN_CLIENT_ID is not configured.")

    try:
        payload = id_token.verify_oauth2_token(raw_token, requests.Request(), _CLIENT_ID)
    except Exception as exc:  # pragma: no cover - google-auth raises many subclasses
        logger.warning("Failed to verify Google ID token: %s", exc)
        raise GoogleIdTokenVerificationError("Google ID 토큰을 검증하지 못했습니다.") from exc

    if _ALLOWED_DOMAIN:
        hosted_domain = payload.get("hd")
        if hosted_domain != _ALLOWED_DOMAIN:
            raise GoogleIdTokenVerificationError("허용된 도메인의 계정이 아닙니다.")

    if not payload.get("email"):
        raise GoogleIdTokenVerificationError("Google ID 토큰에 이메일 정보가 없습니다.")

    if not payload.get("email_verified", False):
        raise GoogleIdTokenVerificationError("Google 계정 이메일이 검증되지 않았습니다.")

    return GoogleIdTokenPayload(
        email=payload["email"],
        subject=payload.get("sub", ""),
        picture=payload.get("picture"),
        name=payload.get("name"),
        hosted_domain=payload.get("hd"),
    )
