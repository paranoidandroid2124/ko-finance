"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from services.plan_guard import PlanGuardError, ensure_entitlement
from services.plan_service import PlanContext, resolve_plan_context
from web.middleware.auth_context import AuthenticatedUser


def get_plan_context(request: Request) -> PlanContext:
    """Fetch the resolved plan context for the current request."""
    context = getattr(request.state, "plan_context", None)
    if context is None:
        context = resolve_plan_context(request.headers)
        request.state.plan_context = context
    return context


def require_plan_feature(entitlement: str):
    """Dependency factory that ensures the active plan exposes the entitlement."""

    def _dependency(plan: PlanContext = Depends(get_plan_context)) -> PlanContext:
        try:
            ensure_entitlement(plan, entitlement)
        except PlanGuardError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.to_detail())
        return plan

    return _dependency


def get_current_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.required", "message": "로그인이 필요한 요청입니다."},
        )
    return user



