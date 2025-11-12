"""Middleware that hydrates RBAC context and handles global enforcement."""

from __future__ import annotations

from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from services.rbac_service import RBAC_ENFORCE_DEFAULT
from web.deps_rbac import resolve_rbac_state

RBAC_BYPASS_PREFIXES = ("/api/v1/auth", "/api/v1/public", "/ops/")


async def rbac_context_middleware(request: Request, call_next: Callable):
    """Attach RBAC state to the request and short-circuit hard failures."""

    path = request.url.path or ""
    should_bypass = any(path.startswith(prefix) for prefix in RBAC_BYPASS_PREFIXES)
    state = resolve_rbac_state(request)

    if (
        RBAC_ENFORCE_DEFAULT
        and not should_bypass
        and state.org_id
        and state.user_id
        and (state.membership is None or state.membership.status != "active")
    ):
        detail = {
            "code": "rbac.membership_required",
            "message": "Active membership required for this workspace.",
        }
        return JSONResponse(status_code=403, content={"detail": detail})

    return await call_next(request)


__all__ = ["rbac_context_middleware"]
