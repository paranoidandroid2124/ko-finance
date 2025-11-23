from __future__ import annotations

import pytest

from fastapi import HTTPException

from services.plan_guard import PlanGuardError, ensure_entitlement, ensure_worker_entitlement
from services.plan_service import PlanContext, PlanQuota
from web.deps import require_plan_feature


def _make_plan(
    *,
    tier: str = "pro",
    entitlements: frozenset[str] | set[str],
) -> PlanContext:
    return PlanContext(
        tier=tier,
        base_tier=tier,
        expires_at=None,
        entitlements=frozenset(entitlements),
        quota=PlanQuota(
            chat_requests_per_day=None,
            rag_top_k=None,
            self_check_enabled=True,
            peer_export_row_limit=None,
        ),
    )


def test_ensure_entitlement_allows_when_feature_enabled() -> None:
    plan = _make_plan(entitlements={"search.export"})
    resolved = ensure_entitlement(plan, "search.export")
    assert resolved is plan


def test_ensure_entitlement_raises_when_missing() -> None:
    plan = _make_plan(tier="free", entitlements=set())
    with pytest.raises(PlanGuardError) as exc:
        ensure_entitlement(plan, "search.export")
    detail = exc.value.to_detail()
    assert detail["code"] == "plan.entitlement_required"
    assert detail["feature"] == "search.export"
    assert detail["planTier"] == "free"


def test_ensure_worker_entitlement_uses_active_context(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _make_plan(entitlements={"evidence.inline_pdf"})

    def fake_context():
        return plan

    monkeypatch.setattr("services.plan_guard.get_active_plan_context", fake_context)
    resolved = ensure_worker_entitlement("evidence.inline_pdf")
    assert resolved is plan


def test_require_plan_feature_dependency_blocks_missing_entitlement() -> None:
    plan = _make_plan(tier="free", entitlements=set())
    dependency = require_plan_feature("rag.core")
    with pytest.raises(HTTPException) as exc:
        dependency(plan=plan)
    assert exc.value.status_code == 403
