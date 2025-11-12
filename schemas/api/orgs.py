"""Pydantic schemas for organisation + RBAC membership endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrgResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: Optional[str]
    status: str
    defaultRole: str = Field(alias="default_role")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class OrgMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    orgId: uuid.UUID = Field(alias="org_id")
    userId: uuid.UUID = Field(alias="user_id")
    role: str
    status: str
    invitedBy: Optional[uuid.UUID] = Field(alias="invited_by", default=None)
    invitedAt: Optional[datetime] = Field(alias="invited_at", default=None)
    acceptedAt: Optional[datetime] = Field(alias="accepted_at", default=None)
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class OrgMemberUpsertRequest(BaseModel):
    userId: uuid.UUID
    role: str = Field(default="viewer")
    status: str = Field(default="pending")


class OrgMemberUpdateRequest(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


class OrgMembershipListResponse(BaseModel):
    memberships: List[OrgMemberResponse]


__all__ = [
    "OrgMemberResponse",
    "OrgMemberUpdateRequest",
    "OrgMemberUpsertRequest",
    "OrgMembershipListResponse",
    "OrgResponse",
]
