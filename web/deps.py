"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from services.plan_service import PlanContext, resolve_plan_context


def get_plan_context(request: Request) -> PlanContext:
    """Fetch the resolved plan context for the current request."""
    context = getattr(request.state, "plan_context", None)
    if context is None:
        context = resolve_plan_context(request)
        request.state.plan_context = context
    return context

