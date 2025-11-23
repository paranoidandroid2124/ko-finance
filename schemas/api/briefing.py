"""Pydantic schemas for F1 daily briefing API."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class BriefingItemSchema(BaseModel):
    title: str = Field(..., description="항목 제목")
    summary: Optional[str] = Field(default=None, description="요약 본문")
    ticker: Optional[str] = Field(default=None, description="관련 티커")
    targetUrl: Optional[str] = Field(default=None, description="연결 링크")


class BriefingResponse(BaseModel):
    id: str = Field(..., description="프로액티브 인사이트 식별자")
    sourceType: str = Field(..., description="항목 타입 (proactive.insight.daily)")
    generatedAt: Optional[str] = Field(default=None, description="생성 시각 (ISO8601)")
    title: Optional[str] = Field(default=None, description="인사이트 제목")
    summary: Optional[str] = Field(default=None, description="인사이트 요약")
    items: List[BriefingItemSchema] = Field(default_factory=list, description="카드 목록")
    meta: Optional[Any] = Field(default=None, description="추가 메타데이터")


__all__ = ["BriefingItemSchema", "BriefingResponse"]
