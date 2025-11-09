"""토큰 발급/검증 및 이메일/비밀번호 재설정용 토큰 스토리지 도우미."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.auth.constants import AuthTokenType
from core.env import env_int, env_str


class AuthTokenError(RuntimeError):
    """토큰 처리 중 발생한 예외."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class MagicToken:
    """DB에 저장되는 단발성 토큰."""

    id: str
    token: str
    token_type: AuthTokenType
    user_id: str
    identifier: str
    expires_at: datetime


_JWT_SECRET = env_str("AUTH_JWT_SECRET") or env_str("AUTH_SECRET")
if not _JWT_SECRET:
    raise RuntimeError("AUTH_JWT_SECRET 또는 AUTH_SECRET 환경 변수가 필요합니다.")

_JWT_ALG = env_str("AUTH_JWT_ALG") or "HS256"
_JWT_ISSUER = env_str("AUTH_JWT_ISSUER") or "kfinance-auth"
_JWT_AUDIENCE = env_str("AUTH_JWT_AUDIENCE") or "dashboard"
_ACCESS_TOKEN_TTL = env_int("AUTH_ACCESS_TOKEN_TTL_SECONDS", 900, minimum=60)
_REFRESH_TOKEN_TTL = env_int("AUTH_REFRESH_TOKEN_TTL_SECONDS", 60 * 60 * 24 * 7, minimum=300)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_magic_token(
    session: Session,
    *,
    user_id: str,
    token_type: AuthTokenType,
    identifier: str,
    expires_in: timedelta,
    metadata: Optional[Dict[str, Any]] = None,
) -> MagicToken:
    """이메일 검증/비밀번호 재설정 등에 사용할 토큰을 생성 후 저장."""

    token = secrets.token_urlsafe(32)
    digest = _token_digest(token)
    expires_at = datetime.now(timezone.utc) + expires_in
    payload = {
        "user_id": user_id,
        "token_type": token_type,
        "identifier": identifier,
        "token_hash": digest,
        "expires_at": expires_at,
        "metadata": json.dumps(metadata or {}),
    }
    row = session.execute(
        text(
            """
            INSERT INTO auth_tokens (user_id, token_hash, token_type, identifier, expires_at, metadata)
            VALUES (:user_id, :token_hash, :token_type, :identifier, :expires_at, CAST(:metadata AS JSONB))
            RETURNING id
            """
        ),
        payload,
    ).mappings().first()
    token_id = str(row["id"])
    return MagicToken(
        id=token_id,
        token=token,
        token_type=token_type,
        user_id=user_id,
        identifier=identifier,
        expires_at=expires_at,
    )


def consume_magic_token(
    session: Session,
    *,
    token: str,
    token_type: AuthTokenType,
) -> MagicToken:
    """토큰을 검증하고 단일 사용 상태로 표기."""

    digest = _token_digest(token)
    row = session.execute(
        text(
            """
            SELECT id, user_id, identifier, expires_at, used_at
            FROM auth_tokens
            WHERE token_hash = :token_hash
              AND token_type = :token_type
            FOR UPDATE
            """
        ),
        {"token_hash": digest, "token_type": token_type},
    ).mappings().first()
    if not row:
        raise AuthTokenError("auth.token_invalid", "유효하지 않은 토큰입니다.")
    now = datetime.now(timezone.utc)
    if row["used_at"]:
        raise AuthTokenError("auth.token_consumed", "이미 사용된 토큰입니다.")
    if row["expires_at"] < now:
        raise AuthTokenError("auth.token_expired", "만료된 토큰입니다.")
    session.execute(
        text("UPDATE auth_tokens SET used_at = NOW() WHERE id = :id"),
        {"id": row["id"]},
    )
    return MagicToken(
        id=str(row["id"]),
        token=token,
        token_type=token_type,
        user_id=str(row["user_id"]),
        identifier=row["identifier"],
        expires_at=row["expires_at"],
    )


def create_access_token(
    *,
    user_id: str,
    email: str,
    plan: str,
    role: str,
    email_verified: bool,
    session_id: Optional[str] = None,
) -> Tuple[str, int]:
    """JWT Access Token 발급."""

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": _JWT_AUDIENCE,
        "iss": _JWT_ISSUER,
        "scope": "access",
        "email": email,
        "plan": plan,
        "role": role,
        "email_verified": email_verified,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_ACCESS_TOKEN_TTL)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if session_id:
        payload["session_id"] = session_id
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)
    return token, _ACCESS_TOKEN_TTL


def create_refresh_token(
    *,
    user_id: str,
    session_id: str,
    refresh_jti: str,
) -> Tuple[str, int]:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": _JWT_AUDIENCE,
        "iss": _JWT_ISSUER,
        "scope": "refresh",
        "session_id": session_id,
        "jti": refresh_jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_REFRESH_TOKEN_TTL)).timestamp()),
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)
    return token, _REFRESH_TOKEN_TTL


def decode_token(token: str, *, scope: Optional[str] = None) -> Dict[str, Any]:
    """JWT 해독 및 scope 확인."""

    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALG],
            audience=_JWT_AUDIENCE,
            issuer=_JWT_ISSUER,
        )
    except jwt.ExpiredSignatureError as exc:  # pragma: no cover - runtime error path
        raise AuthTokenError("auth.token_expired", "토큰이 만료되었습니다.") from exc
    except jwt.InvalidTokenError as exc:  # pragma: no cover - runtime error path
        raise AuthTokenError("auth.token_invalid", "토큰 검증에 실패했습니다.") from exc
    if scope and payload.get("scope") != scope:
        raise AuthTokenError("auth.token_invalid", "토큰 범위가 일치하지 않습니다.")
    return payload


__all__ = [
    "AuthTokenError",
    "AuthTokenType",
    "MagicToken",
    "issue_magic_token",
    "consume_magic_token",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]
