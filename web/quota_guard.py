"""Helper utilities for plan-based entitlement quota enforcement."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from services.entitlement_service import EntitlementDecision
from services.quota_guard import evaluate_quota
from services.plan_service import PlanContext

logger = logging.getLogger(__name__)

_PLAN_LABELS = {
    "free": "Free",
    "starter": "Starter",
    "pro": "Pro",
    "enterprise": "Enterprise",
}

_ACTION_LABELS = {
    "alerts.rules.create": "알림 생성",
    "watchlist.radar": "워치리스트 레이더",
    "watchlist.preview": "다이제스트 미리보기",
    "rag.chat": "AI 분석",
    "api.chat": "Chat API",
}

_PROBLEM_TYPE = "https://nuvien.com/docs/errors/plan-quota"


def enforce_quota(
    action: str,
    *,
    plan: PlanContext,
    user_id: Optional[UUID],
    org_id: Optional[UUID],
    cost: int = 1,
) -> None:
    """Consume the quota for ``action`` and raise RFC7807 errors when exceeded."""

    if user_id is None and org_id is None:
        logger.debug("Skipping quota enforcement for %s: no user/org context provided.", action)
        return

    decision = evaluate_quota(
        action,
        user_id=user_id,
        org_id=org_id,
        cost=cost,
        context="web",
    )
    if decision is None:
        return

    if decision.backend_error:
        logger.warning("Entitlement backend unavailable for action=%s; allowing request.", action)
        return

    if decision.allowed:
        return

    _raise_quota_exception(action=action, plan=plan, decision=decision, cost=cost)


def _raise_quota_exception(
    *,
    action: str,
    plan: PlanContext,
    decision: EntitlementDecision,
    cost: int,
) -> None:
    plan_label = _PLAN_LABELS.get(plan.tier, plan.tier.title())
    action_label = _ACTION_LABELS.get(action, action)
    limit = decision.limit or 0

    if limit == 0:
        status_code = status.HTTP_403_FORBIDDEN
        code = "plan.quota_unavailable"
        message = f"{plan_label} 플랜에서는 {action_label}을(를) 사용할 수 없습니다."
    else:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        code = "plan.quota_exceeded"
        message = f"{plan_label} 플랜 {action_label} 한도를 모두 사용했습니다."

    detail = {
        "type": _PROBLEM_TYPE,
        "title": message,
        "status": status_code,
        "detail": message,
        "code": code,
        "planTier": plan.tier,
        "quota": {
            "action": action,
            "remaining": decision.remaining,
            "limit": decision.limit,
            "cost": cost,
        },
    }

    raise HTTPException(status_code=status_code, detail=detail)
