"""Pydantic schemas for workspace overview endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceMemberSchema(BaseModel):
    userId: UUID = Field(..., description="회원 사용자 ID")
    email: Optional[str] = Field(default=None, description="계정 이메일")
    name: Optional[str] = Field(default=None, description="표시 이름")
    role: str = Field(..., description="조직 내 역할 (viewer/editor/admin).")
    status: str = Field(..., description="멤버십 상태 (active/pending 등)")
    joinedAt: Optional[datetime] = Field(default=None, description="조직 초대 생성 시각")
    acceptedAt: Optional[datetime] = Field(default=None, description="사용자가 초대를 수락한 시각")


class WorkspaceNotebookSchema(BaseModel):
    id: UUID
    title: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    entryCount: int = Field(..., description="노트북 내 엔트리 개수")
    lastActivityAt: Optional[datetime] = None


class WorkspaceWatchlistSchema(BaseModel):
    ruleId: str
    name: str
    type: str = Field(default="watchlist")
    tickers: List[str] = Field(default_factory=list)
    eventCount: int = Field(default=0)
    updatedAt: Optional[datetime] = None


class WorkspaceOverviewResponse(BaseModel):
    orgId: UUID
    orgName: Optional[str] = None
    memberCount: int
    members: List[WorkspaceMemberSchema] = Field(default_factory=list)
    notebooks: List[WorkspaceNotebookSchema] = Field(default_factory=list)
    watchlists: List[WorkspaceWatchlistSchema] = Field(default_factory=list)


__all__ = [
    "WorkspaceMemberSchema",
    "WorkspaceNotebookSchema",
    "WorkspaceOverviewResponse",
    "WorkspaceWatchlistSchema",
]
