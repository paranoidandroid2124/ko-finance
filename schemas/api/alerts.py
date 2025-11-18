"""Schemas for alert rule API contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

AlertChannelType = Literal["email", "telegram", "slack", "webhook", "pagerduty"]
AlertConditionType = Literal["filing", "news"]


class AlertChannelSchema(BaseModel):
    type: AlertChannelType = Field(..., description="Delivery channel identifier.")
    target: Optional[str] = Field(default=None, description="Primary channel-specific target (email, webhook URL 등).")
    targets: List[str] = Field(default_factory=list, description="Optional additional recipients for the channel.")
    label: Optional[str] = Field(default=None, description="Display label for the channel.")
    template: Optional[str] = Field(default=None, description="Template identifier to override the default payload.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Channel-specific configuration metadata.")

    @field_validator("target", "label", "template", mode="before")
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value

    @field_validator("targets", mode="before")
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

    @field_validator("metadata", mode="before")
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


class AlertTriggerSchema(BaseModel):
    type: AlertConditionType = Field(default="filing", description="알림 대상 데이터 타입.")
    tickers: List[str] = Field(default_factory=list, description="감시할 티커 목록.")
    categories: List[str] = Field(default_factory=list, description="공시 카테고리 필터.")
    sectors: List[str] = Field(default_factory=list, description="섹터/산업 필터 (뉴스 조건).")
    minSentiment: Optional[float] = Field(
        default=None,
        description="뉴스 감성 임계값 (type=news에만 적용).",
    )
    keywords: List[str] = Field(default_factory=list, description="키워드 필터 (헤드라인/보고서 제목 검색).")
    entities: List[str] = Field(default_factory=list, description="엔터티/회사명 필터.")
    dsl: Optional[str] = Field(
        default=None,
        description="고급 DSL 표현식 (예: \"news ticker:005930 keyword:'자사주' window:24h\").",
    )

    @field_validator("tickers", "categories", "sectors", "keywords", "entities", mode="before")
    def _strip_values(cls, value: Any):
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [item.strip() if isinstance(item, str) else item for item in value]
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        return value

    @field_validator("dsl", mode="before")
    def _normalize_dsl(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value)


# Legacy alias for backwards compatibility
AlertConditionSchema = AlertTriggerSchema


class AlertFrequencySchema(BaseModel):
    evaluationIntervalMinutes: int = Field(default=5, ge=1, le=1440, description="평가 주기(분).")
    windowMinutes: int = Field(default=60, ge=5, le=1440, description="이벤트 탐색 윈도우(분).")
    cooldownMinutes: int = Field(default=60, ge=0, le=1440, description="발송 이후 쿨다운(분).")
    maxTriggersPerDay: Optional[int] = Field(default=None, ge=1, le=200, description="일일 발송 제한.")

    @model_validator(mode="after")
    def _ensure_window_bounds(self) -> "AlertFrequencySchema":
        if self.windowMinutes < self.evaluationIntervalMinutes:
            self.windowMinutes = self.evaluationIntervalMinutes
        return self


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., max_length=120, description="Alert rule title.")
    description: Optional[str] = Field(default=None, description="Optional description/note.")
    trigger: AlertTriggerSchema = Field(default_factory=AlertTriggerSchema, description="Structured trigger definition.")
    frequency: AlertFrequencySchema = Field(
        default_factory=AlertFrequencySchema,
        description="Evaluation/cooldown settings applied to the trigger.",
    )
    channels: List[AlertChannelSchema] = Field(default_factory=list)
    messageTemplate: Optional[str] = Field(default=None, description="Optional message template (Python format style).")
    extras: Dict[str, str] = Field(default_factory=dict, description="Additional metadata.")


class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None)
    trigger: Optional[AlertTriggerSchema] = Field(default=None, description="Structured trigger payload.")
    frequency: Optional[AlertFrequencySchema] = Field(
        default=None, description="Updated evaluation/cooldown configuration."
    )
    channels: Optional[List[AlertChannelSchema]] = Field(default=None)
    messageTemplate: Optional[str] = Field(default=None)
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
    frequencyDefaults: Dict[str, Optional[int]]
    nextEvaluationAt: Optional[str] = None


class AlertRulePreset(BaseModel):
    id: str
    bundle: str
    bundleLabel: Optional[str] = None
    planTiers: List[str] = Field(default_factory=list)
    name: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    sampleDsl: Optional[str] = None
    recommendedChannel: Optional[AlertChannelType] = None
    trigger: AlertTriggerSchema
    frequency: AlertFrequencySchema
    insight: Optional[str] = None
    priority: Optional[int] = None


class AlertRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    planTier: str
    status: str
    trigger: Dict[str, Any]
    triggerType: str = Field(default="filing", description="정규화된 트리거 타입.")
    filters: Dict[str, Any] = Field(default_factory=dict, description="트리거에서 추출한 필터 값.")
    state: Dict[str, Any] = Field(default_factory=dict, description="최근 평가 상태/스로틀 메타데이터.")
    channelFailures: Dict[str, Any] = Field(default_factory=dict, description="채널별 최근 실패 현황.")
    frequency: Dict[str, Any]
    channels: List[Dict[str, Any]]
    messageTemplate: Optional[str]
    evaluationIntervalMinutes: int
    windowMinutes: int
    cooldownMinutes: int
    maxTriggersPerDay: Optional[int]
    lastTriggeredAt: Optional[str]
    lastEvaluatedAt: Optional[str]
    cooledUntil: Optional[str]
    throttleUntil: Optional[str]
    errorCount: int
    extras: Dict[str, Any]
    createdAt: Optional[str]
    updatedAt: Optional[str]


class AlertRuleLastDelivery(BaseModel):
    id: str
    status: str
    channel: Optional[str] = None
    error: Optional[str] = None
    createdAt: Optional[str] = None


class AlertRuleSimulationRequest(BaseModel):
    windowMinutes: Optional[int] = Field(
        default=None,
        ge=5,
        le=7 * 24 * 60,
        description="Optional override for rule lookback window.",
    )
    limit: Optional[int] = Field(
        default=5,
        ge=1,
        le=50,
        description="Max number of matched events to return.",
    )


class AlertRuleSimulationResponse(BaseModel):
    ruleId: str
    planTier: str
    evaluatedAt: str
    matches: bool
    eventType: str
    message: str
    windowMinutes: int
    windowStart: str
    windowEnd: str
    eventCount: int
    events: List[Dict[str, Any]] = Field(default_factory=list)
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class AlertRuleStatsResponse(BaseModel):
    ruleId: str
    windowMinutes: Optional[int] = None
    total: int
    delivered: int
    failed: int
    throttled: int
    lastDelivery: Optional[AlertRuleLastDelivery] = None


class AlertEventMatchSchema(BaseModel):
    eventId: str
    alertId: str
    ruleName: str
    eventType: str
    ticker: Optional[str] = None
    corpName: Optional[str] = None
    eventDate: Optional[str] = None
    domain: Optional[str] = None
    subtype: Optional[str] = None
    matchScore: Optional[float] = None
    matchedAt: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlertEventMatchResponse(BaseModel):
    matches: List[AlertEventMatchSchema]


class AlertRuleListResponse(BaseModel):
    items: List[AlertRuleResponse]
    plan: AlertPlanInfo
    presets: List[AlertRulePreset] = Field(default_factory=list)


class WatchlistRadarSummary(BaseModel):
    totalDeliveries: int
    totalEvents: int
    uniqueTickers: int
    topTickers: List[str] = Field(default_factory=list)
    topChannels: Dict[str, int] = Field(default_factory=dict)
    topRules: List[str] = Field(default_factory=list)
    failedDeliveries: int = 0
    channelFailures: Dict[str, int] = Field(default_factory=dict)
    windowStart: Optional[str] = None
    windowEnd: Optional[str] = None


class WatchlistRadarItem(BaseModel):
    deliveryId: str
    ruleId: str
    ruleName: str
    channel: str
    eventType: str
    ruleTags: List[str] = Field(default_factory=list)
    ruleTickers: List[str] = Field(default_factory=list)
    deliveryStatus: str
    deliveryError: Optional[str] = None
    ruleErrorCount: int = 0
    ticker: Optional[str] = None
    company: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[float] = None
    message: Optional[str] = None
    deliveredAt: str
    eventTime: Optional[str] = None
    url: Optional[str] = None


class WatchlistRadarResponse(BaseModel):
    generatedAt: str
    windowMinutes: int
    window: Dict[str, str]
    summary: WatchlistRadarSummary
    items: List[WatchlistRadarItem]


class WatchlistDispatchResult(BaseModel):
    channel: str
    status: str
    delivered: int
    failed: int
    error: Optional[str] = None


class WatchlistDispatchResponse(BaseModel):
    summary: WatchlistRadarSummary
    results: List[WatchlistDispatchResult]


class WatchlistDispatchRequest(BaseModel):
    windowMinutes: Optional[int] = Field(default=1440, ge=5, le=7 * 24 * 60)
    limit: Optional[int] = Field(default=20, ge=1, le=200)
    slackTargets: Optional[List[str]] = Field(default=None)
    emailTargets: Optional[List[str]] = Field(default=None)


class WatchlistDigestScheduleSchema(BaseModel):
    id: UUID
    label: str
    timeOfDay: str
    timezone: str
    weekdaysOnly: bool
    windowMinutes: int
    limit: int
    slackTargets: List[str] = Field(default_factory=list)
    emailTargets: List[str] = Field(default_factory=list)
    enabled: bool
    nextDispatchAt: Optional[str] = None
    lastDispatchedAt: Optional[str] = None
    lastStatus: Optional[str] = None
    lastError: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class WatchlistDigestScheduleListResponse(BaseModel):
    items: List[WatchlistDigestScheduleSchema]


class WatchlistDigestScheduleCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    timeOfDay: str = Field(..., pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Seoul", min_length=3, max_length=64)
    weekdaysOnly: bool = Field(default=True)
    windowMinutes: int = Field(default=1440, ge=5, le=7 * 24 * 60)
    limit: int = Field(default=20, ge=1, le=200)
    slackTargets: List[str] = Field(default_factory=list, max_items=20)
    emailTargets: List[str] = Field(default_factory=list, max_items=20)
    enabled: bool = Field(default=True)


class WatchlistDigestScheduleUpdateRequest(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=80)
    timeOfDay: Optional[str] = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: Optional[str] = Field(default=None, min_length=3, max_length=64)
    weekdaysOnly: Optional[bool] = None
    windowMinutes: Optional[int] = Field(default=None, ge=5, le=7 * 24 * 60)
    limit: Optional[int] = Field(default=None, ge=1, le=200)
    slackTargets: Optional[List[str]] = Field(default=None, max_items=20)
    emailTargets: Optional[List[str]] = Field(default=None, max_items=20)
    enabled: Optional[bool] = None


class WatchlistDigestPreviewRequest(BaseModel):
    windowMinutes: Optional[int] = Field(default=None, ge=5, le=7 * 24 * 60)
    limit: Optional[int] = Field(default=None, ge=1, le=500)


class WatchlistDigestPreviewResponse(BaseModel):
    schedule: WatchlistDigestScheduleSchema
    payload: Dict[str, Any]


class WatchlistRuleChannelSummary(BaseModel):
    type: str
    label: Optional[str] = None
    target: Optional[str] = None
    targets: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WatchlistRuleConditionDetail(BaseModel):
    type: str
    tickers: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    sectors: List[str] = Field(default_factory=list)
    minSentiment: Optional[float] = None


class WatchlistDeliveryEventDetail(BaseModel):
    ticker: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[float] = None
    category: Optional[str] = None
    url: Optional[str] = None
    eventTime: Optional[str] = None


class WatchlistDeliveryLog(BaseModel):
    deliveryId: str
    channel: str
    status: str
    deliveredAt: str
    error: Optional[str] = None
    eventCount: int
    events: List[WatchlistDeliveryEventDetail] = Field(default_factory=list)


class WatchlistRuleDetail(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    evaluationIntervalMinutes: int
    windowMinutes: int
    cooldownMinutes: int
    maxTriggersPerDay: Optional[int] = None
    trigger: WatchlistRuleConditionDetail
    channels: List[WatchlistRuleChannelSummary] = Field(default_factory=list)
    extras: Dict[str, Any] = Field(default_factory=dict)
    lastTriggeredAt: Optional[str] = None
    lastEvaluatedAt: Optional[str] = None
    errorCount: int = 0


class WatchlistRuleDetailResponse(BaseModel):
    rule: WatchlistRuleDetail
    recentDeliveries: List[WatchlistDeliveryLog] = Field(default_factory=list)
    totalDeliveries: int = 0
    failedDeliveries: int = 0
