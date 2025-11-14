"""Onboarding content + completion routes."""

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
    OnboardingSampleBoardSchema,
    OnboardingSampleSectionSchema,
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


@router.get("/content", response_model=OnboardingContentResponse, summary="온보딩 콘텐츠를 반환합니다.")
def read_onboarding_content(request: Request, db: Session = Depends(get_db)) -> OnboardingContentResponse:
    user = _require_user(request)
    needs_onboarding = onboarding_service.user_needs_onboarding(db, user_id=user.id)
    content = onboarding_service.load_onboarding_content()
    hero = OnboardingHeroSchema(**content.get("hero", {}))
    checklist = [OnboardingChecklistItemSchema(**item) for item in content.get("checklist", [])]
    sample_sections = [OnboardingSampleSectionSchema(**section) for section in content.get("sampleBoard", {}).get("sections", [])]
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
