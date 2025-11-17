"""Pydantic schemas for onboarding content + wizard APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field

from core.plan_constants import PlanTier


class OnboardingCtaSchema(BaseModel):
    label: str = Field(..., description="CTA 레이블")
    href: str = Field(..., description="CTA 링크 또는 경로")


class OnboardingChecklistItemSchema(BaseModel):
    id: str = Field(..., description="체크리스트 항목 ID")
    title: str = Field(..., description="체크리스트 제목")
    description: str = Field(..., description="설명")
    tips: List[str] = Field(default_factory=list, description="추가 팁 문장 목록")
    cta: Optional[OnboardingCtaSchema] = Field(default=None, description="CTA 링크 정보")


class OnboardingSampleSectionSchema(BaseModel):
    id: str = Field(..., description="샘플 섹션 ID")
    title: str = Field(..., description="섹션 제목")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="샘플 카드 리스트")


class OnboardingSampleBoardSchema(BaseModel):
    title: str = Field(..., description="샘플 보드 제목")
    sections: List[OnboardingSampleSectionSchema] = Field(default_factory=list)


class OnboardingHeroSchema(BaseModel):
    title: str = Field(...)
    subtitle: str = Field(...)
    highlights: List[str] = Field(default_factory=list)


class OnboardingContentResponse(BaseModel):
    onboardingRequired: bool = Field(..., description="true면 추가 온보딩이 필요합니다.")
    hero: OnboardingHeroSchema
    checklist: List[OnboardingChecklistItemSchema]
    sampleBoard: OnboardingSampleBoardSchema


class OnboardingPlanOptionSchema(BaseModel):
    tier: PlanTier
    title: str
    tagline: Optional[str] = None
    badge: Optional[str] = None
    priceAmount: Optional[int] = Field(default=None, description="표시용 가격 금액")
    priceCurrency: Optional[str] = None
    priceInterval: Optional[str] = None
    features: List[str] = Field(default_factory=list)


class OnboardingOrgSchema(BaseModel):
    id: uuid.UUID
    name: str
    slug: Optional[str] = None
    planTier: PlanTier
    planStatus: str
    membershipRole: str
    membershipStatus: str
    memberCount: int
    currentPeriodEnd: Optional[datetime] = None


class OnboardingMemberSchema(BaseModel):
    userId: uuid.UUID
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: str
    status: str
    invitedAt: Optional[datetime] = None
    acceptedAt: Optional[datetime] = None


class OnboardingWizardStateResponse(BaseModel):
    onboardingRequired: bool
    org: OnboardingOrgSchema
    members: List[OnboardingMemberSchema]
    planOptions: List[OnboardingPlanOptionSchema]


class OnboardingOrgUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    slug: Optional[str] = Field(default=None, description="조직 슬러그 (URL 식별자)")


class OnboardingOrgResponse(BaseModel):
    org: OnboardingOrgSchema


class OnboardingInviteEntry(BaseModel):
    email: EmailStr
    role: Optional[str] = Field(default="viewer", description="viewer/editor/admin")
    status: Optional[str] = Field(default="pending", description="pending/active")


class OnboardingInviteRequest(BaseModel):
    orgId: uuid.UUID
    invites: List[OnboardingInviteEntry]


class OnboardingMembersResponse(BaseModel):
    members: List[OnboardingMemberSchema]


class OnboardingPlanSelectRequest(BaseModel):
    orgId: uuid.UUID
    planTier: PlanTier


class OnboardingSlugAvailabilityResponse(BaseModel):
    slug: str
    available: bool


class OnboardingCompleteRequest(BaseModel):
    completedSteps: List[str] = Field(default_factory=list, description="완료한 체크리스트 ID 목록")


class OnboardingCompleteResponse(BaseModel):
    onboardingRequired: bool = Field(..., description="완료 후 온보딩 필요 여부")


__all__ = [
    "OnboardingChecklistItemSchema",
    "OnboardingCompleteRequest",
    "OnboardingCompleteResponse",
    "OnboardingContentResponse",
    "OnboardingInviteRequest",
    "OnboardingMemberSchema",
    "OnboardingMembersResponse",
    "OnboardingOrgResponse",
    "OnboardingOrgSchema",
    "OnboardingOrgUpdateRequest",
    "OnboardingPlanOptionSchema",
    "OnboardingPlanSelectRequest",
    "OnboardingSlugAvailabilityResponse",
    "OnboardingSampleBoardSchema",
    "OnboardingWizardStateResponse",
]
