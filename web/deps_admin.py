"""Admin authentication dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import HTTPException, Request, status

from core.env import env_str
from core.logging import get_logger
from database import SessionLocal
from services.admin_session_service import (
    SESSION_COOKIE_NAME,
    AdminSessionRecord,
    validate_admin_session,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class AdminSession:
    """Represents a validated administrator session."""

    actor: str
    issued_at: datetime
    token_hint: Optional[str] = None
    session_id: Optional[str] = None
    expires_at: Optional[datetime] = None


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": code, "message": message})


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return f"{token[:2]}***{token[-2:]}"


def load_admin_token_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    tokens_env = env_str("ADMIN_API_TOKENS")
    default_actor = env_str("ADMIN_API_ACTOR", "admin") or "admin"

    if tokens_env:
        for entry in tokens_env.split(","):
            entry = entry.strip()
            if not entry:
                continue
            actor: Optional[str] = None
            token: Optional[str] = None
            if ":" in entry:
                actor, token = entry.split(":", 1)
            elif "=" in entry:
                actor, token = entry.split("=", 1)
            else:
                token = entry
            actor = (actor or default_actor).strip() or "admin"
            token = (token or "").strip()
            if token:
                mapping[token] = actor

    single_token = env_str("ADMIN_API_TOKEN")
    if single_token:
        mapping[single_token.strip()] = default_actor

    return mapping


def _extract_admin_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        candidate = auth_header[7:].strip()
        if candidate:
            return candidate
    header_token = request.headers.get("x-admin-token")
    if header_token:
        return header_token.strip()
    return None


def _validate_session_cookie(request: Request) -> Optional[AdminSessionRecord]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    db = SessionLocal()
    try:
        return validate_admin_session(db, token=token, touch=True)
    finally:
        db.close()


def require_admin_session(
    request: Request,
    *,
    error_code: str = "admin.unauthorized",
) -> AdminSession:
    """
    Validate that the current request carries a recognised admin credential.

    Validation order:
    1. Signed admin session cookie (preferred, server-issued)
    2. Authorization: Bearer <token>
    3. X-Admin-Token header
    """

    cookie_record = _validate_session_cookie(request)
    if cookie_record:
        session = AdminSession(
            actor=cookie_record.actor,
            issued_at=cookie_record.issued_at,
            token_hint=cookie_record.token_hint,
            session_id=cookie_record.id,
            expires_at=cookie_record.expires_at,
        )
        request.state.admin_session = session
        return session

    token_map = load_admin_token_map()
    if not token_map:
        logger.error("ADMIN_API_TOKEN or ADMIN_API_TOKENS is not configured; admin access blocked.")
        raise _forbidden(error_code, "관리자 인증 설정이 준비되지 않았어요. 운영 팀에 문의해주세요.")

    provided = _extract_admin_token(request)
    if not provided:
        logger.warning("Admin access denied: missing credential.")
        raise _forbidden(error_code, "관리자 권한이 필요해요. 먼저 로그인하거나 토큰을 확인해주세요.")

    actor = token_map.get(provided)
    if not actor:
        logger.warning("Admin access denied: invalid token %s.", _mask_token(provided))
        raise _forbidden(error_code, "관리자 토큰이 올바르지 않아요. 새 토큰을 발급받아 주세요.")

    actor_override = request.headers.get("x-admin-actor")
    if actor_override:
        actor_override = actor_override.strip()
        if actor_override:
            actor = actor_override

    session = AdminSession(
        actor=actor,
        issued_at=datetime.now(timezone.utc),
        token_hint=_mask_token(provided),
    )
    request.state.admin_session = session
    return session


def require_admin_session_for_plan(request: Request) -> AdminSession:
    """Specialised dependency for plan routes with custom error code."""
    return require_admin_session(request, error_code="plan.unauthorized")
