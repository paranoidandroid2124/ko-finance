"""Onboarding content + wizard routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.onboarding import (
    OnboardingChecklistItemSchema,
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    OnboardingContentResponse,
    OnboardingHeroSchema,
    OnboardingInviteRequest,
    OnboardingMemberSchema,
    OnboardingMembersResponse,
    OnboardingOrgResponse,
    OnboardingOrgSchema,
    OnboardingOrgUpdateRequest,
    OnboardingPlanOptionSchema,
    OnboardingPlanSelectRequest,
    OnboardingSampleBoardSchema,
    OnboardingSampleSectionSchema,
    OnboardingSlugAvailabilityResponse,
    OnboardingWizardStateResponse,
)
from services import onboarding_service
from web.middleware.auth_context import AuthenticatedUser

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def _require_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.required", "message": "로그인이 필요한 요청입니다."},
        )
    return user


def _serialize_org(org: onboarding_service.OnboardingOrgState) -> OnboardingOrgSchema:
    return OnboardingOrgSchema(
        id=org.id,
        name=org.name,
        slug=org.slug,
        planTier=org.plan_tier,
        planStatus=org.plan_status,
        membershipRole=org.membership_role,
        membershipStatus=org.membership_status,
        memberCount=org.member_count,
        currentPeriodEnd=org.current_period_end,
    )


def _serialize_member(member: onboarding_service.OnboardingMemberRecord) -> OnboardingMemberSchema:
    return OnboardingMemberSchema(
        userId=member.user_id,
        email=member.email,
        name=member.name,
        role=member.role,
        status=member.status,
        invitedAt=member.invited_at,
        acceptedAt=member.accepted_at,
    )


def _serialize_plan_option(option: onboarding_service.OnboardingPlanOption) -> OnboardingPlanOptionSchema:
    return OnboardingPlanOptionSchema(
        tier=option.tier,
        title=option.title,
        tagline=option.tagline,
        badge=option.badge,
        priceAmount=option.price_amount,
        priceCurrency=option.price_currency,
        priceInterval=option.price_interval,
        features=option.features,
    )


@router.get("/content", response_model=OnboardingContentResponse, summary="온보딩 콘텐츠를 반환합니다.")
def read_onboarding_content(request: Request, db: Session = Depends(get_db)) -> OnboardingContentResponse:
    user = _require_user(request)
    needs_onboarding = onboarding_service.user_needs_onboarding(db, user_id=user.id)
    content = onboarding_service.load_onboarding_content()
    hero = OnboardingHeroSchema(**content.get("hero", {}))
    checklist = [OnboardingChecklistItemSchema(**item) for item in content.get("checklist", [])]
    sample_sections = [
        OnboardingSampleSectionSchema(**section) for section in content.get("sampleBoard", {}).get("sections", [])
    ]
    sample_board = OnboardingSampleBoardSchema(
        title=content.get("sampleBoard", {}).get("title", "샘플 리서치 허브"),
        sections=sample_sections,
    )
    return OnboardingContentResponse(
        onboardingRequired=needs_onboarding,
        hero=hero,
        checklist=checklist,
        sampleBoard=sample_board,
    )


@router.get("/state", response_model=OnboardingWizardStateResponse, summary="온보딩 위저드 상태를 조회합니다.")
def read_onboarding_state(request: Request, db: Session = Depends(get_db)) -> OnboardingWizardStateResponse:
    user = _require_user(request)
    state = onboarding_service.load_onboarding_wizard_state(db, user_id=user.id)
    return OnboardingWizardStateResponse(
        onboardingRequired=state.onboarding_required,
        org=_serialize_org(state.org),
        members=[_serialize_member(member) for member in state.members],
        planOptions=[_serialize_plan_option(option) for option in state.plan_options],
    )


@router.post("/org", response_model=OnboardingOrgResponse, summary="조직 프로필을 생성 또는 업데이트합니다.")
def upsert_org(
    payload: OnboardingOrgUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OnboardingOrgResponse:
    user = _require_user(request)
    try:
        org_state = onboarding_service.upsert_org_profile(
            db,
            user_id=user.id,
            name=payload.name,
            slug=payload.slug,
        )
    except ValueError as exc:
        if str(exc) == "slug_taken":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "onboarding.slug_taken", "message": "이미 사용 중인 슬러그입니다."},
            ) from exc
        raise
    return OnboardingOrgResponse(org=_serialize_org(org_state))


@router.get(
    "/org/slug/{slug}",
    response_model=OnboardingSlugAvailabilityResponse,
    summary="조직 슬러그 사용 가능 여부를 확인합니다.",
)
def check_org_slug(slug: str, request: Request, db: Session = Depends(get_db)) -> OnboardingSlugAvailabilityResponse:
    user = _require_user(request)
    state = onboarding_service.load_onboarding_wizard_state(db, user_id=user.id)
    available = onboarding_service.is_slug_available(db, slug=slug, exclude_org_id=state.org.id)
    return OnboardingSlugAvailabilityResponse(slug=slug, available=available)


@router.post("/invite", response_model=OnboardingMembersResponse, summary="조직 구성원을 초대합니다.")
def invite_members(
    payload: OnboardingInviteRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OnboardingMembersResponse:
    user = _require_user(request)
    try:
        members = onboarding_service.invite_org_members(
            db,
            actor_id=user.id,
            org_id=payload.orgId,
            invites=[invite.model_dump() for invite in payload.invites],
        )
    except ValueError as exc:
        code = str(exc)
        if code == "membership_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "onboarding.membership_not_found", "message": "조직 멤버십을 찾을 수 없습니다."},
            ) from exc
        if code in {"role_insufficient", "membership_inactive"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": f"onboarding.{code}", "message": "조직 초대 권한이 없습니다."},
            ) from exc
        raise
    return OnboardingMembersResponse(members=[_serialize_member(member) for member in members])


@router.post("/plan", response_model=OnboardingOrgResponse, summary="조직의 플랜을 선택합니다.")
def select_org_plan(
    payload: OnboardingPlanSelectRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OnboardingOrgResponse:
    user = _require_user(request)
    try:
        org_state = onboarding_service.select_plan_for_org(
            db,
            user_id=user.id,
            org_id=payload.orgId,
            plan_tier=payload.planTier,
        )
    except ValueError as exc:
        code = str(exc)
        if code in {"membership_not_found", "role_insufficient", "membership_inactive"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": f"onboarding.{code}", "message": "조직 플랜을 변경할 수 없습니다."},
            ) from exc
        raise
    return OnboardingOrgResponse(org=_serialize_org(org_state))


@router.post("/complete", response_model=OnboardingCompleteResponse, summary="온보딩 완료 상태를 저장합니다.")
def complete_onboarding(
    payload: OnboardingCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> OnboardingCompleteResponse:
    user = _require_user(request)
    with db.begin():
        onboarding_service.mark_onboarding_completed(
            db,
            user_id=user.id,
            completed_steps=payload.completedSteps,
        )
    return OnboardingCompleteResponse(onboardingRequired=False)
