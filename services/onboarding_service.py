"""Helpers for onboarding state and sample content."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.env import env_int
from core.logging import get_logger
from core.plan_constants import PlanTier, SUPPORTED_PLAN_TIERS
from services.entitlement_service import entitlement_service
from services.file_store import write_json_atomic
from services.plan_catalog_service import load_plan_catalog
from services.workspace_bootstrap import bootstrap_workspace_for_org

logger = get_logger(__name__)

_ONBOARDING_TRIAL_DAYS = env_int("ONBOARDING_TRIAL_DAYS", 14, minimum=1)
_ONBOARDING_PLAN_PERIOD_DAYS = env_int("ONBOARDING_PLAN_PERIOD_DAYS", 30, minimum=7)

_ONBOARDING_CONTENT_PATH = Path("uploads") / "admin" / "onboarding_samples.json"
_ONBOARDING_CONTENT_CACHE: Optional[Dict[str, Any]] = None

_DEFAULT_ONBOARDING_CONTENT: Dict[str, Any] = {
    "hero": {
        "title": "어서 오세요! 첫 3분 리서치 루틴을 안내해 드릴게요",
        "subtitle": "워치리스트·챗봇·리포트까지, 샘플 보드를 통해 하루 업무 플로우를 체험할 수 있습니다.",
        "highlights": [
            "공시/뉴스 모니터링 핵심만 추려서 보여드려요",
            "AI 애널리스트 답변과 근거 Diff 를 함께 확인할 수 있어요",
            "샘플 워크보드를 복사해서 바로 팀 공유 가능합니다",
        ],
    },
    "checklist": [
        {
            "id": "chat-rag",
            "title": "AI 애널리스트에게 질문",
            "description": "Evidence-first 답변과 Diff 뷰어를 체험해 보세요.",
            "tips": ["질문 템플릿을 사용하면 더욱 빠르게 분석 시작!"],
            "cta": {"label": "샘플 질문 실행", "href": "/chat?sample=onboarding"},
        },
        {
            "id": "report-preview",
            "title": "AI 리포트 미리보기",
            "description": "생성형 리포트가 어떤 흐름으로 구성되는지 샘플로 확인해 보세요.",
            "tips": ["Slack/Email 채널 링크를 통해 팀 공유도 가능합니다."],
            "cta": {"label": "샘플 리포트 보기", "href": "/reports"},
        },
    ],
    "sampleBoard": {
        "title": "샘플 리서치 허브",
        "sections": [
            {
                "id": "alerts",
                "title": "금일 감지된 공시/뉴스",
                "items": [
                    {
                        "type": "alert",
                        "badge": "공시",
                        "headline": "삼성전자, 1.5조 규모 파운드리 투자",
                        "summary": "시설투자 확대와 더불어 파운드리 라인 전환 계획을 공시했습니다.",
                        "link": "/chat",
                        "meta": {"ticker": "005930.KS", "publishedAt": "오늘 09:10"},
                    },
                    {
                        "type": "news",
                        "badge": "뉴스",
                        "headline": "배터리 3사, IRA 세액공제 확대 수혜",
                        "summary": "미 에너지부 가이드라인 변경으로 국내 셀 업체들의 수혜 폭이 커질 전망입니다.",
                        "link": "/chat",
                        "meta": {"ticker": "373220.KS", "publishedAt": "오늘 08:45"},
                    },
                ],
            },
            {
                "id": "chat",
                "title": "AI 애널리스트 Q&A",
                "items": [
                    {
                        "type": "chat",
                        "question": "2분기 삼성전자 실적과 전년 동기 대비 관전 포인트는?",
                        "answerPreview": "메모리 ASP 하락으로 YoY 감소했으나, HBM 수요확대로 하반기 턴어라운드 기대...",
                        "link": "/chat?sample=earnings",
                    }
                ],
            },
            {
                "id": "reports",
                "title": "AI 리포트 샘플",
                "items": [
                    {
                        "type": "report",
                        "headline": "전력·에너지 정책 업데이트",
                        "bullets": [
                            "산업부, 신재생 발전 비중 2030년 32% 목표",
                            "에너지 공기업, 2분기부터 REC 의무비율 상향 예정",
                        ],
                        "link": "/reports",
                    }
                ],
            },
        ],
    },
}


def _slugify(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
    normalized = "-".join(filter(None, normalized.split("-"))).strip("-")
    return normalized[:60] or None


def _is_slug_taken(session: Session, slug: str, *, exclude_org_id: Optional[uuid.UUID] = None) -> bool:
    clause = "LOWER(slug) = LOWER(:slug)"
    params: Dict[str, Any] = {"slug": slug}
    if exclude_org_id:
        clause += " AND id != :org_id"
        params["org_id"] = str(exclude_org_id)
    row = session.execute(text(f"SELECT 1 FROM orgs WHERE {clause} LIMIT 1"), params).first()
    return bool(row)


def _lookup_primary_membership(session: Session, user_id: uuid.UUID) -> Optional[Mapping[str, Any]]:
    return (
        session.execute(
            text(
                """
                SELECT
                    uo.org_id,
                    uo.role_key,
                    uo.status,
                    o.name,
                    o.slug
                FROM user_orgs uo
                JOIN orgs o ON o.id = uo.org_id
                WHERE uo.user_id = :user_id
                ORDER BY uo.created_at ASC
                LIMIT 1
                """
            ),
            {"user_id": str(user_id)},
        )
        .mappings()
        .first()
    )


def _create_personal_org(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: Optional[str],
    slug: Optional[str],
    strict_slug: bool = False,
) -> uuid.UUID:
    org_id = uuid.uuid4()
    display_name = (name or f"Workspace {str(user_id)[:8]}").strip()
    safe_slug = _slugify(slug)
    if safe_slug and _is_slug_taken(session, safe_slug):
        if strict_slug:
            raise ValueError("slug_taken")
        safe_slug = None
    session.execute(
        text(
            """
            INSERT INTO orgs (id, name, slug, status, default_role, metadata)
            VALUES (:id, :name, :slug, 'active', 'viewer', '{}'::jsonb)
            """
        ),
        {"id": str(org_id), "name": display_name, "slug": safe_slug},
    )
    session.execute(
        text(
            """
            INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at)
            VALUES (:org_id, :user_id, 'admin', 'active', :user_id, NOW(), NOW())
            ON CONFLICT (org_id, user_id) DO NOTHING
            """
        ),
        {"org_id": str(org_id), "user_id": str(user_id)},
    )
    bootstrap_workspace_for_org(org_id=org_id, owner_id=user_id, source="onboarding.create_personal_org")
    return org_id


def _ensure_primary_org(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: Optional[str] = None,
    slug: Optional[str] = None,
    strict_slug: bool = False,
) -> Mapping[str, Any]:
    membership = _lookup_primary_membership(session, user_id)
    if membership:
        return membership
    org_id = _create_personal_org(session, user_id=user_id, name=name, slug=slug, strict_slug=strict_slug)
    return {
        "org_id": org_id,
        "role_key": "admin",
        "status": "active",
        "name": name or f"Workspace {str(user_id)[:8]}",
        "slug": _slugify(slug),
    }


def _resolve_plan_status(session: Session, org_id: uuid.UUID) -> tuple[PlanTier, str, Optional[datetime]]:
    row = (
        session.execute(
            text(
                """
                SELECT p.slug, os.status, os.current_period_end
                FROM org_subscriptions os
                JOIN plans p ON p.id = os.plan_id
                WHERE os.org_id = :org_id
                ORDER BY os.updated_at DESC
                LIMIT 1
                """
            ),
            {"org_id": str(org_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        return "free", "active", None
    slug = str(row["slug"] or "free").strip().lower()
    plan_tier: PlanTier = slug if slug in SUPPORTED_PLAN_TIERS else "free"
    status = (row.get("status") or "active").strip().lower()
    return plan_tier, status, row.get("current_period_end")


def _load_subscription_metadata(session: Session, org_id: uuid.UUID) -> Mapping[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT metadata
                FROM org_subscriptions
                WHERE org_id = :org_id
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"org_id": str(org_id)},
        )
        .mappings()
        .first()
    )
    metadata = row["metadata"] if row else None
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def _list_members(session: Session, org_id: uuid.UUID) -> List[OnboardingMemberRecord]:
    rows = session.execute(
        text(
            """
            SELECT
                uo.user_id,
                u.email,
                u.name,
                uo.role_key,
                uo.status,
                uo.invited_at,
                uo.accepted_at
            FROM user_orgs uo
            LEFT JOIN users u ON u.id = uo.user_id
            WHERE uo.org_id = :org_id
            ORDER BY uo.created_at ASC
            """
        ),
        {"org_id": str(org_id)},
    ).mappings()
    members: List[OnboardingMemberRecord] = []
    for row in rows:
        members.append(
            OnboardingMemberRecord(
                user_id=uuid.UUID(str(row["user_id"])),
                email=row.get("email"),
                name=row.get("name"),
                role=str(row.get("role_key") or "viewer"),
                status=str(row.get("status") or "active"),
                invited_at=row.get("invited_at"),
                accepted_at=row.get("accepted_at"),
            )
        )
    return members


def _plan_options_from_catalog() -> List[OnboardingPlanOption]:
    catalog = load_plan_catalog()
    tiers = catalog.get("tiers") or []
    entries: Sequence[Any]
    if isinstance(tiers, Mapping):
        entries = list(tiers.values())
    elif isinstance(tiers, Sequence):
        entries = tiers
    else:
        entries = []
    options: List[OnboardingPlanOption] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        tier = str(entry.get("tier") or "").strip().lower()
        if tier not in SUPPORTED_PLAN_TIERS:
            continue
        price = entry.get("price") or {}
        price_amount = price.get("amount") if isinstance(price, Mapping) else None
        price_currency = price.get("currency") if isinstance(price, Mapping) else None
        price_interval = price.get("interval") if isinstance(price, Mapping) else None
        features_raw = entry.get("features") or []
        features: List[str] = []
        for feature in features_raw:
            if isinstance(feature, Mapping):
                text_value = feature.get("text")
            else:
                text_value = feature
            if text_value:
                features.append(str(text_value))
        options.append(
            OnboardingPlanOption(
                tier=tier,  # type: ignore[assignment]
                title=str(entry.get("title") or tier.title()),
                tagline=str(entry.get("tagline") or ""),
                badge=entry.get("badge"),
                price_amount=price_amount if isinstance(price_amount, (int, float)) else None,
                price_currency=str(price_currency) if price_currency else None,
                price_interval=str(price_interval) if price_interval else None,
                features=features,
            )
        )
    return options


def _build_org_state(
    *,
    org_id: uuid.UUID,
    membership: Mapping[str, Any],
    plan_tier: PlanTier,
    plan_status: str,
    current_period_end: Optional[datetime],
    members: Sequence[OnboardingMemberRecord],
) -> OnboardingOrgState:
    return OnboardingOrgState(
        id=org_id,
        name=str(membership.get("name") or f"Workspace {str(org_id)[:8]}"),
        slug=membership.get("slug"),
        plan_tier=plan_tier,
        plan_status=plan_status,
        membership_role=str(membership.get("role_key") or "viewer"),
        membership_status=str(membership.get("status") or "active"),
        member_count=len(members),
        current_period_end=current_period_end,
    )


def _assert_org_admin(session: Session, *, org_id: uuid.UUID, user_id: uuid.UUID) -> Mapping[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT role_key, status
                FROM user_orgs
                WHERE org_id = :org_id
                  AND user_id = :user_id
                """
            ),
            {"org_id": str(org_id), "user_id": str(user_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError("membership_not_found")
    if str(row.get("status") or "active") != "active":
        raise ValueError("membership_inactive")
    if str(row.get("role_key") or "viewer") != "admin":
        raise ValueError("role_insufficient")
    return row


def _load_org_metadata(session: Session, org_id: uuid.UUID) -> Mapping[str, Any]:
    row = (
        session.execute(
            text("SELECT name, slug FROM orgs WHERE id = :org_id"),
            {"org_id": str(org_id)},
        )
        .mappings()
        .first()
    )
    return row or {"name": f"Workspace {str(org_id)[:8]}", "slug": None}



@dataclass(frozen=True)
class OnboardingPlanOption:
    tier: PlanTier
    title: str
    tagline: Optional[str]
    badge: Optional[str]
    price_amount: Optional[int]
    price_currency: Optional[str]
    price_interval: Optional[str]
    features: List[str]


@dataclass(frozen=True)
class OnboardingMemberRecord:
    user_id: uuid.UUID
    email: Optional[str]
    name: Optional[str]
    role: str
    status: str
    invited_at: Optional[datetime]
    accepted_at: Optional[datetime]


@dataclass(frozen=True)
class OnboardingOrgState:
    id: uuid.UUID
    name: str
    slug: Optional[str]
    plan_tier: PlanTier
    plan_status: str
    membership_role: str
    membership_status: str
    member_count: int
    current_period_end: Optional[datetime]


@dataclass(frozen=True)
class OnboardingWizardState:
    org: OnboardingOrgState
    members: List[OnboardingMemberRecord]
    plan_options: List[OnboardingPlanOption]
    onboarding_required: bool


def load_onboarding_content(*, reload: bool = False) -> Dict[str, Any]:
    global _ONBOARDING_CONTENT_CACHE
    if _ONBOARDING_CONTENT_CACHE is not None and not reload:
        return deepcopy(_ONBOARDING_CONTENT_CACHE)

    path = _ONBOARDING_CONTENT_PATH
    if not path.exists():
        write_json_atomic(path, _DEFAULT_ONBOARDING_CONTENT, logger=logger)
        payload = deepcopy(_DEFAULT_ONBOARDING_CONTENT)
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load onboarding samples from %s: %s", path, exc)
            payload = deepcopy(_DEFAULT_ONBOARDING_CONTENT)

    _ONBOARDING_CONTENT_CACHE = deepcopy(payload)
    return deepcopy(payload)


def load_onboarding_wizard_state(session: Session, *, user_id: str) -> OnboardingWizardState:
    user_uuid = uuid.UUID(str(user_id))
    membership = _ensure_primary_org(session, user_id=user_uuid)
    org_id = membership["org_id"] if isinstance(membership["org_id"], uuid.UUID) else uuid.UUID(str(membership["org_id"]))
    plan_tier, plan_status, current_period_end = _resolve_plan_status(session, org_id)
    members = _list_members(session, org_id)
    org_state = _build_org_state(
        org_id=org_id,
        membership=membership,
        plan_tier=plan_tier,
        plan_status=plan_status,
        current_period_end=current_period_end,
        members=members,
    )
    return OnboardingWizardState(
        org=org_state,
        members=members,
        plan_options=_plan_options_from_catalog(),
        onboarding_required=user_needs_onboarding(session, user_id=user_id),
    )


def upsert_org_profile(
    session: Session,
    *,
    user_id: str,
    name: str,
    slug: Optional[str],
) -> OnboardingOrgState:
    user_uuid = uuid.UUID(str(user_id))
    membership = _ensure_primary_org(session, user_id=user_uuid, name=name, slug=slug, strict_slug=bool(slug))
    org_id = membership["org_id"] if isinstance(membership["org_id"], uuid.UUID) else uuid.UUID(str(membership["org_id"]))
    safe_slug = _slugify(slug)
    if safe_slug and _is_slug_taken(session, safe_slug, exclude_org_id=org_id):
        raise ValueError("slug_taken")
    trimmed_name = name.strip() or f"Workspace {str(user_uuid)[:8]}"
    session.execute(
        text(
            """
            UPDATE orgs
            SET name = :name,
                slug = :slug,
                updated_at = NOW()
            WHERE id = :org_id
            """
        ),
        {"name": trimmed_name, "slug": safe_slug, "org_id": str(org_id)},
    )
    membership = {
        **membership,
        "name": trimmed_name,
        "slug": safe_slug,
    }
    members = _list_members(session, org_id)
    plan_tier, plan_status, current_period_end = _resolve_plan_status(session, org_id)
    return _build_org_state(
        org_id=org_id,
        membership=membership,
        plan_tier=plan_tier,
        plan_status=plan_status,
        current_period_end=current_period_end,
        members=members,
    )


def invite_org_members(
    session: Session,
    *,
    actor_id: str,
    org_id: uuid.UUID,
    invites: Sequence[Mapping[str, Any]],
) -> List[OnboardingMemberRecord]:
    actor_uuid = uuid.UUID(str(actor_id))
    _assert_org_admin(session, org_id=org_id, user_id=actor_uuid)
    if not invites:
        return _list_members(session, org_id)

    now = datetime.now(timezone.utc)
    for payload in invites:
        email_raw = str(payload.get("email") or "").strip()
        if not email_raw:
            continue
        normalized_email = email_raw.lower()
        user_row = (
            session.execute(
                text('SELECT id, email, name FROM "users" WHERE LOWER(email) = :email'),
                {"email": normalized_email},
            )
            .mappings()
            .first()
        )
        if user_row:
            invited_user_id = uuid.UUID(str(user_row["id"]))
        else:
            inserted = (
                session.execute(
                    text(
                        """
                        INSERT INTO "users" (email, name, signup_channel, plan_tier, role)
                        VALUES (:email_original, NULL, 'admin_invite', 'free', 'user')
                        RETURNING id
                        """
                    ),
                    {"email_original": email_raw},
                )
                .mappings()
                .first()
            )
            invited_user_id = uuid.UUID(str(inserted["id"]))
        requested_role = str(payload.get("role") or "viewer").strip().lower()
        role_key = requested_role if requested_role in {"viewer", "editor", "admin"} else "viewer"
        requested_status = str(payload.get("status") or "pending").strip().lower()
        status_value = requested_status if requested_status in {"active", "pending"} else "pending"
        session.execute(
            text(
                """
                INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at)
                VALUES (:org_id, :user_id, :role_key, :status, :invited_by, :invited_at,
                        CASE WHEN :status = 'active' THEN :invited_at ELSE NULL END)
                ON CONFLICT (org_id, user_id) DO UPDATE SET
                    role_key = EXCLUDED.role_key,
                    status = EXCLUDED.status,
                    invited_by = COALESCE(user_orgs.invited_by, EXCLUDED.invited_by),
                    invited_at = COALESCE(user_orgs.invited_at, EXCLUDED.invited_at),
                    accepted_at = CASE
                        WHEN EXCLUDED.status = 'active' THEN COALESCE(user_orgs.accepted_at, EXCLUDED.accepted_at)
                        ELSE user_orgs.accepted_at
                    END,
                    updated_at = NOW()
                """
            ),
            {
                "org_id": str(org_id),
                "user_id": str(invited_user_id),
                "role_key": role_key,
                "status": status_value,
                "invited_by": str(actor_uuid),
                "invited_at": now,
            },
        )
    return _list_members(session, org_id)


def is_slug_available(
    session: Session,
    *,
    slug: str,
    exclude_org_id: Optional[uuid.UUID] = None,
) -> bool:
    normalized = _slugify(slug)
    if not normalized:
        return False
    return not _is_slug_taken(session, normalized, exclude_org_id=exclude_org_id)


def select_plan_for_org(
    session: Session,
    *,
    user_id: str,
    org_id: uuid.UUID,
    plan_tier: PlanTier,
) -> OnboardingOrgState:
    actor_uuid = uuid.UUID(str(user_id))
    _assert_org_admin(session, org_id=org_id, user_id=actor_uuid)
    normalized_plan = plan_tier if plan_tier in SUPPORTED_PLAN_TIERS else "free"
    previous_metadata = _load_subscription_metadata(session, org_id)
    plan_resolved_before, plan_status_before, _ = _resolve_plan_status(session, org_id)
    trial_previously_used = bool(previous_metadata.get("trialUsed"))
    trial_enabled = normalized_plan == PlanTier.PRO and not trial_previously_used
    now = datetime.now(timezone.utc)
    duration_days = _ONBOARDING_TRIAL_DAYS if trial_enabled else _ONBOARDING_PLAN_PERIOD_DAYS
    status = "trialing" if trial_enabled else "active"
    metadata = {
        "source": "onboarding.plan_select",
        "actor": str(actor_uuid),
        "selectedTier": normalized_plan.value if isinstance(normalized_plan, PlanTier) else str(normalized_plan),
        "trialUsed": trial_enabled or trial_previously_used,
    }
    if trial_enabled:
        metadata["trialEndsAt"] = (now + timedelta(days=duration_days)).isoformat()
        metadata["trialOrigin"] = "onboarding"
        metadata["previousTier"] = plan_resolved_before
    entitlement_service.sync_subscription_from_billing(
        org_id=org_id,
        plan_slug=normalized_plan,
        status=status,
        current_period_end=now + timedelta(days=duration_days),
        metadata=metadata,
    )
    org_metadata = _load_org_metadata(session, org_id)
    membership = {
        "name": org_metadata.get("name"),
        "slug": org_metadata.get("slug"),
        "role_key": "admin",
        "status": "active",
    }
    members = _list_members(session, org_id)
    plan_resolved, plan_status, current_period_end = _resolve_plan_status(session, org_id)
    return _build_org_state(
        org_id=org_id,
        membership=membership,
        plan_tier=plan_resolved,
        plan_status=plan_status,
        current_period_end=current_period_end,
        members=members,
    )


def ensure_first_login_metadata(session: Session, *, user_id: str) -> bool:
    row = (
        session.execute(
            text(
                """
                SELECT first_login_at, onboarded_at
                FROM "users"
                WHERE id = :user_id
                FOR UPDATE
                """
            ),
            {"user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        return False

    if row["first_login_at"] is None:
        session.execute(
            text("UPDATE \"users\" SET first_login_at = :now WHERE id = :user_id"),
            {"now": datetime.now(timezone.utc), "user_id": user_id},
        )
    return row.get("onboarded_at") is None


def mark_onboarding_completed(
    session: Session,
    *,
    user_id: str,
    completed_steps: Optional[Sequence[str]],
) -> None:
    checklist_json = json.dumps({"steps": list(dict.fromkeys(completed_steps or []))}, ensure_ascii=False)
    session.execute(
        text(
            """
            UPDATE "users"
            SET onboarded_at = COALESCE(onboarded_at, NOW()),
                onboarding_checklist = CAST(:checklist AS JSONB)
            WHERE id = :user_id
            """
        ),
        {"checklist": checklist_json, "user_id": user_id},
    )


def user_needs_onboarding(session: Session, *, user_id: str) -> bool:
    row = session.execute(
        text("SELECT onboarded_at FROM \"users\" WHERE id = :user_id"),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        return False
    return row.get("onboarded_at") is None


__all__ = [
    "OnboardingMemberRecord",
    "OnboardingOrgState",
    "OnboardingPlanOption",
    "OnboardingWizardState",
    "ensure_first_login_metadata",
    "invite_org_members",
    "load_onboarding_content",
    "load_onboarding_wizard_state",
    "mark_onboarding_completed",
    "is_slug_available",
    "select_plan_for_org",
    "upsert_org_profile",
    "user_needs_onboarding",
]
