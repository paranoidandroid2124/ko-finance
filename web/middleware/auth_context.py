"""Attach authenticated user information from Authorization headers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from core.logging import get_logger
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
