"""Plan entitlement enforcement helpers used across API and workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from services.plan_service import PlanContext, get_active_plan_context

_FEATURE_LABELS: Dict[str, str] = {
    "search.compare": "비교 검색",
    "search.alerts": "알림 자동화",
    "search.export": "데이터 내보내기",
    "evidence.inline_pdf": "Evidence PDF",
    "evidence.diff": "Evidence Diff",
    "timeline.full": "전체 타임라인",
    "table.explorer": "Table Explorer",
}


@dataclass(slots=True)
class PlanGuardError(RuntimeError):
    """Raised when the active plan does not satisfy a required entitlement."""

    code: str
    message: str
    feature: Optional[str] = None
    plan_tier: Optional[str] = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def to_detail(self) -> Dict[str, Optional[str]]:
        detail: Dict[str, Optional[str]] = {
            "code": self.code,
            "message": self.message,
        }
        if self.feature:
            detail["feature"] = self.feature
        if self.plan_tier:
            detail["planTier"] = self.plan_tier
        return detail


def _feature_label(entitlement: str) -> str:
    return _FEATURE_LABELS.get(entitlement, entitlement)


def ensure_entitlement(plan: PlanContext, entitlement: str) -> PlanContext:
    """Validate that the provided plan context includes the entitlement."""

    if plan.allows(entitlement):
        return plan
    label = _feature_label(entitlement)
    raise PlanGuardError(
        code="plan.entitlement_required",
        message=f"현재 플랜({plan.tier})에서는 '{label}' 기능을 사용할 수 없습니다.",
        feature=entitlement,
        plan_tier=plan.tier,
    )


def ensure_worker_entitlement(entitlement: str) -> PlanContext:
    """Validate entitlements for background tasks that do not run inside FastAPI."""

    plan = get_active_plan_context()
    return ensure_entitlement(plan, entitlement)


__all__ = ["PlanGuardError", "ensure_entitlement", "ensure_worker_entitlement"]
