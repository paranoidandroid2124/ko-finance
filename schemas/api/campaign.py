"Campaign settings schema."

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CampaignEmailTemplateSchema(BaseModel):
    id: str = Field(..., description="Template identifier (e.g., starter_trial_invite).")
    subject: str
    preview: Optional[str] = None
    bodyTemplate: str = Field(..., description="Path to the template file or identifier.")


class StarterCampaignBannerSchema(BaseModel):
    headline: str
    body: str
    ctaLabel: str
    dismissLabel: str


class StarterCampaignSettingsSchema(BaseModel):
    enabled: bool = False
    banner: StarterCampaignBannerSchema
    emails: List[CampaignEmailTemplateSchema] = []
    kpi: dict = Field(default_factory=dict)


class CampaignSettingsResponse(BaseModel):
    starter_promo: StarterCampaignSettingsSchema
