"""Schemas for alert rule API contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator

AlertChannelType = Literal["email", "telegram", "slack", "webhook", "pagerduty"]
AlertConditionType = Literal["filing", "news"]


class AlertChannelSchema(BaseModel):
    type: AlertChannelType = Field(..., description="Delivery channel identifier.")
    target: Optional[str] = Field(default=None, description="Primary channel-specific target (email, webhook URL 등).")
    targets: List[str] = Field(default_factory=list, description="Optional additional recipients for the channel.")
    label: Optional[str] = Field(default=None, description="Display label for the channel.")
    template: Optional[str] = Field(default=None, description="Template identifier to override the default payload.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Channel-specific configuration metadata.")

    @validator("target", "label", "template", pre=True)
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @validator("targets", pre=True)
    def _normalize_targets(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            cleaned: List[str] = []
            for item in value:
                if not isinstance(item, str):
                    continue
                stripped = item.strip()
                if stripped and stripped not in cleaned:
                    cleaned.append(stripped)
            return cleaned
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        return []

    @validator("metadata", pre=True)
    def _ensure_metadata_dict(cls, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}


RuleType = Literal["required", "regex", "min_length", "enum"]


class AlertChannelRule(BaseModel):
    type: RuleType = Field(..., description="Validation rule type identifier.")
    message: str = Field(..., description="Human-readable validation error message.")
    pattern: Optional[str] = Field(default=None, description="Regex pattern for regex rules.")
    flags: Optional[str] = Field(default=None, description="Regex flags (e.g., 'i' for IGNORECASE).")
    value: Optional[int] = Field(default=None, description="Numeric value for min_length rules.")
    values: Optional[List[str]] = Field(default=None, description="Allowed values for enum rules.")
    collectInvalid: bool = Field(default=False, description="Collect invalid inputs and project into the message.")
    optional: bool = Field(default=False, description="Skip rule when the field is empty.")


class AlertChannelValidationDefinition(BaseModel):
    type: AlertChannelType
    requiresTarget: bool = Field(default=False, description="Indicates whether the channel expects at least one target.")
    targetRules: List[AlertChannelRule] = Field(default_factory=list, description="Validation rules for channel targets.")
    metadataRules: Dict[str, List[AlertChannelRule]] = Field(default_factory=dict, description="Validation rules per metadata key.")


class AlertChannelSchemaResponse(BaseModel):
    channels: List[AlertChannelValidationDefinition]


class AlertConditionSchema(BaseModel):
    type: AlertConditionType = Field(default="filing", description="알림 대상 데이터 타입.")
    tickers: List[str] = Field(default_factory=list, description="감시할 티커 목록.")
    categories: List[str] = Field(default_factory=list, description="공시 카테고리 필터.")
    sectors: List[str] = Field(default_factory=list, description="섹터/산업 필터 (뉴스 조건).")
    minSentiment: Optional[float] = Field(
        default=None,
        description="뉴스 감성 임계값 (type=news에만 적용).",
    )

    @validator("tickers", "categories", "sectors", pre=True, each_item=True)
    def _strip_values(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., max_length=120, description="알림 이름.")
    description: Optional[str] = Field(default=None, description="설명/메모.")
    condition: AlertConditionSchema = Field(default_factory=AlertConditionSchema)
    channels: List[AlertChannelSchema] = Field(default_factory=list)
    messageTemplate: Optional[str] = Field(default=None, description="선택적 메시지 템플릿(파이썬 format 스타일).")
    evaluationIntervalMinutes: int = Field(default=5, ge=1, le=1440, description="평가 주기(분).")
    windowMinutes: int = Field(default=60, ge=5, le=1440, description="이벤트 탐색 윈도우(분).")
    cooldownMinutes: int = Field(default=60, ge=0, le=1440, description="발송 후 쿨다운(분).")
    maxTriggersPerDay: Optional[int] = Field(default=None, ge=1, le=200, description="일일 발송 제한.")
    extras: Dict[str, str] = Field(default_factory=dict, description="추가 저장용 메타데이터.")


class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None)
    condition: Optional[AlertConditionSchema] = Field(default=None)
    channels: Optional[List[AlertChannelSchema]] = Field(default=None)
    messageTemplate: Optional[str] = Field(default=None)
    evaluationIntervalMinutes: Optional[int] = Field(default=None, ge=1, le=1440)
    windowMinutes: Optional[int] = Field(default=None, ge=5, le=1440)
    cooldownMinutes: Optional[int] = Field(default=None, ge=0, le=1440)
    maxTriggersPerDay: Optional[int] = Field(default=None, ge=1, le=200)
    status: Optional[Literal["active", "paused", "archived"]] = Field(default=None)
    extras: Optional[Dict[str, str]] = Field(default=None)


class AlertPlanInfo(BaseModel):
    planTier: str
    maxAlerts: int
    remainingAlerts: int
    channels: List[str]
    maxDailyTriggers: Optional[int] = None
    defaultEvaluationIntervalMinutes: int
    defaultWindowMinutes: int
    defaultCooldownMinutes: int
    minEvaluationIntervalMinutes: int
    minCooldownMinutes: int
    nextEvaluationAt: Optional[str] = None


class AlertRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    planTier: str
    status: str
    condition: Dict[str, Any]
    channels: List[Dict[str, Any]]
    messageTemplate: Optional[str]
    evaluationIntervalMinutes: int
    windowMinutes: int
    cooldownMinutes: int
    maxTriggersPerDay: Optional[int]
    lastTriggeredAt: Optional[str]
    lastEvaluatedAt: Optional[str]
    throttleUntil: Optional[str]
    errorCount: int
    extras: Dict[str, Any]
    createdAt: Optional[str]
    updatedAt: Optional[str]


class AlertRuleListResponse(BaseModel):
    items: List[AlertRuleResponse]
    plan: AlertPlanInfo
