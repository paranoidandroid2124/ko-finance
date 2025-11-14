"""Pydantic schemas for onboarding content + completion APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OnboardingCtaSchema(BaseModel):
    label: str = Field(..., description="?? ??")
    href: str = Field(..., description="??/?? ??")


class OnboardingChecklistItemSchema(BaseModel):
    id: str = Field(..., description="????? ???")
    title: str = Field(..., description="????? ??")
    description: str = Field(..., description="??")
    tips: List[str] = Field(default_factory=list, description="??? ? ??")
    cta: Optional[OnboardingCtaSchema] = Field(default=None, description="CTA ?? ??")


class OnboardingSampleSectionSchema(BaseModel):
    id: str = Field(..., description="?? ID")
    title: str = Field(..., description="?? ??")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="??? ?? ???")


class OnboardingSampleBoardSchema(BaseModel):
    title: str = Field(..., description="?? ?? ??")
    sections: List[OnboardingSampleSectionSchema] = Field(default_factory=list)


class OnboardingHeroSchema(BaseModel):
    title: str = Field(...)
    subtitle: str = Field(...)
    highlights: List[str] = Field(default_factory=list)


class OnboardingContentResponse(BaseModel):
    onboardingRequired: bool = Field(..., description="true? ??? ??")
    hero: OnboardingHeroSchema
    checklist: List[OnboardingChecklistItemSchema]
    sampleBoard: OnboardingSampleBoardSchema


class OnboardingCompleteRequest(BaseModel):
    completedSteps: List[str] = Field(default_factory=list, description="???? ??? ????? ID")


class OnboardingCompleteResponse(BaseModel):
    onboardingRequired: bool = Field(..., description="?? ?? ? ?? ??")


__all__ = [
    "OnboardingChecklistItemSchema",
    "OnboardingContentResponse",
    "OnboardingCompleteRequest",
    "OnboardingCompleteResponse",
]
