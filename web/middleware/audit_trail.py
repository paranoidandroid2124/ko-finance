"""Middleware that records audit trails for admin and export endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Request

from core.logging import get_logger
from database import SessionLocal
from services.admin_session_service import record_admin_audit_event
from services.audit_log import record_audit_event

logger = get_logger(__name__)

_ADMIN_PATH_PREFIXES = ("/ops/", "/api/v1/admin")
_EXPORT_PATH_PREFIXES = (
    "/api/v1/reports",
    "/api/v1/table-explorer/export",
)


def _maybe_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _is_admin_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _ADMIN_PATH_PREFIXES)


def _is_export_path(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in _EXPORT_PATH_PREFIXES):
        return True
    return "/export" in path


async def audit_trail_middleware(request: Request, call_next):
    response = None
    captured_exc: Optional[Exception] = None
    try:
        response = await call_next(request)
        return response
    except Exception as exc:  # pragma: no cover - passthrough to upstream handlers
        captured_exc = exc
        raise
    finally:
        try:
            _record_admin_audit(request, response, captured_exc)
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("Failed to record admin audit trail.")
        try:
            _record_export_audit(request, response, captured_exc)
        except Exception:  # pragma: no cover - best effort logging
            logger.exception("Failed to record export audit trail.")


def _record_admin_audit(request: Request, response, captured_exc: Optional[Exception]) -> None:
    path = request.url.path if request.url else ""
    if not _is_admin_path(path):
        return
    admin_session = getattr(request.state, "admin_session", None)
    if not admin_session:
        return
    status_code = getattr(response, "status_code", 500 if captured_exc else 200)
    db = SessionLocal()
    try:
        record_admin_audit_event(
            db,
            actor=admin_session.actor,
            event_type="request",
            session_id=getattr(admin_session, "session_id", None),
            route=path,
            method=request.method.upper(),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={
                "status_code": status_code,
                "query": request.url.query if request.url else "",
                "error": bool(captured_exc),
            },
        )
    finally:
        db.close()


def _record_export_audit(request: Request, response, captured_exc: Optional[Exception]) -> None:
    path = request.url.path if request.url else ""
    if not _is_export_path(path):
        return
    user = getattr(request.state, "user", None)
    plan_context = getattr(request.state, "plan_context", None)
    feature_flags = None
    if plan_context and hasattr(plan_context, "feature_flags"):
        try:
            feature_flags = plan_context.feature_flags()
        except Exception:
            feature_flags = None
    status_code = getattr(response, "status_code", 500 if captured_exc else 200)
    extra = {
        "method": request.method.upper(),
        "status_code": status_code,
        "query": request.url.query if request.url else "",
        "error": bool(captured_exc),
    }
    if user:
        extra.update(
            {
                "user_id": getattr(user, "id", None),
                "user_role": getattr(user, "role", None),
                "plan_tier": getattr(user, "plan", None),
            }
        )
    record_audit_event(
        action="api.export_request",
        source="api",
        user_id=_maybe_uuid(getattr(user, "id", None)) if user else None,
        org_id=None,
        target_id=path,
        feature_flags=feature_flags,
        extra=extra,
    )


__all__ = ["audit_trail_middleware"]
