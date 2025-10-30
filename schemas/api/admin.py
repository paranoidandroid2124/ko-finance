"""Admin 영역 API 스키마."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

PlanTier = Literal["free", "pro", "enterprise"]


class WebhookAuditEntrySchema(BaseModel):
    loggedAt: Optional[str] = Field(default=None, description="감사 로그가 기록된 시각 (UTC).")
    result: str = Field(..., description="처리 결과 식별자.")
    message: Optional[str] = Field(default=None, description="추가 설명 또는 오류 메시지.")
    context: Dict[str, Any] = Field(default_factory=dict, description="웹훅 처리 메타데이터.")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="웹훅 원본 페이로드.")


class WebhookAuditListResponse(BaseModel):
    items: List[WebhookAuditEntrySchema] = Field(default_factory=list, description="웹훅 감사 로그 목록.")


class PlanQuickAdjustQuota(BaseModel):
    chatRequestsPerDay: Optional[int] = Field(default=None)
    ragTopK: Optional[int] = Field(default=None)
    selfCheckEnabled: Optional[bool] = Field(default=None)
    peerExportRowLimit: Optional[int] = Field(default=None)


class PlanQuickAdjustRequest(BaseModel):
    planTier: PlanTier = Field(..., description="적용할 플랜 티어.")
    entitlements: List[str] = Field(default_factory=list, description="플랜에 부여할 권한 목록.")
    quota: Optional[PlanQuickAdjustQuota] = Field(default=None, description="선택적 쿼터 오버라이드.")
    expiresAt: Optional[str] = Field(default=None, description="ISO8601 만료 일시.")
    actor: str = Field(..., min_length=1, max_length=200, description="조치를 수행한 운영자 식별자.")
    changeNote: Optional[str] = Field(default=None, max_length=500, description="변경 사유 또는 메모.")
    triggerCheckout: bool = Field(default=False, description="토스 결제 체크아웃을 강제로 시작할지 여부.")
    forceCheckoutRequested: Optional[bool] = Field(
        default=None,
        description="checkoutRequested 플래그를 명시적으로 설정/해제할 때 사용합니다.",
    )

    @field_validator("entitlements", mode="before")
    def _normalize_entitlements(cls, value: Optional[List[str]]) -> List[str]:
        if not value:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized


class TossWebhookReplayRequest(BaseModel):
    transmissionId: str = Field(..., description="재처리할 Toss webhook transmission ID.")


class TossWebhookReplayResponse(BaseModel):
    status: str = Field(..., description="웹훅 이벤트 상태 값.")
    orderId: Optional[str] = Field(default=None, description="연관된 orderId.")
    tier: Optional[PlanTier] = Field(default=None, description="재처리로 적용된 플랜 티어.")
    noop: Optional[bool] = Field(default=None, description="실행할 작업이 없어 건너뛴 경우 true.")


__all__ = [
    "PlanQuickAdjustQuota",
    "PlanQuickAdjustRequest",
    "WebhookAuditEntrySchema",
    "WebhookAuditListResponse",
    "TossWebhookReplayRequest",
    "TossWebhookReplayResponse",
]
