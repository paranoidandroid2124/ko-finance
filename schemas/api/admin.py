"""Schemas for admin dashboard APIs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AdminUserResponse(BaseModel):
    id: str
    email: str
    plan: str
    isActive: bool
    reportCount: int
    lastReportAt: Optional[datetime]
    lastLoginAt: Optional[datetime]


class AdminUserListResponse(BaseModel):
    users: List[AdminUserResponse]


class AdminUserUpdateRequest(BaseModel):
    plan: Optional[str] = None
    isActive: Optional[bool] = None


class AdminKpiResponse(BaseModel):
    totalUsers: int
    reportsToday: int
    heavyUsers: int


__all__ = [
    "AdminUserResponse",
    "AdminUserListResponse",
    "AdminUserUpdateRequest",
    "AdminKpiResponse",
]
