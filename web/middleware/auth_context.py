"""Attach authenticated user information from Authorization headers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.logging import get_logger
from database import SessionLocal
from services.auth_tokens import AuthTokenError, decode_token
from services.user_service import fetch_user_by_id

logger = get_logger(__name__)

_BYPASS_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/public",
    "/ops/",
    "/docs",
    "/openapi",
    "/health",
    "/metrics",
)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    plan: str
    role: str
    email_verified: bool


_SESSION_ERROR_MESSAGES = {
    "auth.session_required": "세션 정보가 누락되었습니다. 다시 로그인해 주세요.",
    "auth.session_invalid": "세션 정보를 확인할 수 없습니다. 다시 로그인해 주세요.",
    "auth.session_revoked": "세션이 종료되었습니다. 다시 로그인해 주세요.",
    "auth.session_expired": "세션이 만료되었습니다. 다시 로그인해 주세요.",
    "auth.session_check_failed": "세션 검증 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}


def _should_bypass(path: str) -> bool:
    path = path or ""
    return any(path.startswith(prefix) for prefix in _BYPASS_PREFIXES)


def _extract_bearer(header_value: Optional[str]) -> Optional[str]:
    if not header_value:
        return None
    value = header_value.strip()
    if not value:
        return None
    if value.lower().startswith("bearer "):
        token = value[7:].strip()
        return token or None
    return None


def _validate_session_active(session_id: Optional[str]) -> Tuple[bool, Optional[str], int]:
    if not session_id:
        return False, "auth.session_required", status.HTTP_401_UNAUTHORIZED
    try:
        db = SessionLocal()
    except Exception as exc:  # pragma: no cover - guard against misconfiguration
        logger.error("Failed to initialise SessionLocal for session validation: %s", exc)
        return False, "auth.session_check_failed", status.HTTP_503_SERVICE_UNAVAILABLE
    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT revoked_at, expires_at
                    FROM session_tokens
                    WHERE id = :session_id
                    """
                ),
                {"session_id": session_id},
            )
            .mappings()
            .first()
        )
    except Exception as exc:  # pragma: no cover - DB failure
        logger.warning("Session validation query failed for session_id=%s: %s", session_id, exc, exc_info=True)
        return False, "auth.session_check_failed", status.HTTP_503_SERVICE_UNAVAILABLE
    finally:
        db.close()

    if not row:
        return False, "auth.session_invalid", status.HTTP_401_UNAUTHORIZED
    now = datetime.now(timezone.utc)
    revoked_at = row.get("revoked_at")
    expires_at = row.get("expires_at")
    if revoked_at:
        return False, "auth.session_revoked", status.HTTP_401_UNAUTHORIZED
    if expires_at and expires_at < now:
        return False, "auth.session_expired", status.HTTP_401_UNAUTHORIZED
    return True, None, status.HTTP_200_OK


async def auth_context_middleware(request: Request, call_next):
    path = request.url.path if request.url else ""
    if request.method == "OPTIONS" or _should_bypass(path):
        return await call_next(request)

    token = _extract_bearer(request.headers.get("authorization"))
    if not token:
        return await call_next(request)

    try:
        payload = decode_token(token, scope="access")
    except AuthTokenError as exc:
        detail = {"code": exc.code, "message": str(exc)}
        status_code = 401 if exc.code in {"auth.token_expired", "auth.token_invalid"} else 400
        return JSONResponse(status_code=status_code, content={"detail": detail})

    user_id = payload.get("sub")
    if not user_id:
        detail = {"code": "auth.token_invalid", "message": "유효하지 않은 토큰입니다."}
        return JSONResponse(status_code=401, content={"detail": detail})

    is_active, error_code, status_code = _validate_session_active(payload.get("session_id"))
    if not is_active:
        message = _SESSION_ERROR_MESSAGES.get(error_code or "", "세션 상태를 확인할 수 없습니다.")
        detail = {"code": error_code or "auth.session_invalid", "message": message}
        return JSONResponse(status_code=status_code, content={"detail": detail})

    record = fetch_user_by_id(str(user_id))

    if not record:
        detail = {"code": "auth.user_not_found", "message": "사용자를 찾을 수 없습니다."}
        return JSONResponse(status_code=401, content={"detail": detail})

    plan = record.plan_tier or payload.get("plan") or "free"
    role = record.role or payload.get("role") or "user"
    auth_user = AuthenticatedUser(
        id=record.id,
        email=record.email,
        plan=plan,
        role=role,
        email_verified=record.email_verified,
    )
    request.state.user = auth_user
    request.state.user_claims = payload
    return await call_next(request)


__all__ = ["AuthenticatedUser", "auth_context_middleware"]
