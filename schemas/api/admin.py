"""Admin 영역 API 스키마."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.plan_constants import PlanTier
from schemas.api.plan import PlanMemoryFlagsSchema
PromptChannel = Literal["chat", "rag", "self_check"]


class AdminBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AdminLlmProfileSchema(AdminBaseModel):
    name: str = Field(..., description="설정할 프로필 이름.")
    model: str = Field(..., description="기본으로 사용할 모델 ID 또는 Alias.")
    settings: Dict[str, Any] = Field(default_factory=dict, description="temperature, maxTokens 등 모델 세부 설정.")


class AdminLlmProfileListResponse(AdminBaseModel):
    profiles: List[AdminLlmProfileSchema] = Field(default_factory=list, description="LiteLLM 프로필 목록.")


class AdminLlmProfileUpsertRequest(AdminLlmProfileSchema):
    actor: str = Field(..., description="변경을 수행하는 운영자 식별자.")
    note: Optional[str] = Field(default=None, description="변경 사유 또는 메모.")


class AdminLlmProfileResponse(AdminBaseModel):
    profile: AdminLlmProfileSchema = Field(..., description="업데이트된 LiteLLM 프로필.")
    updatedAt: str = Field(..., description="변경 시각(ISO8601).")
    updatedBy: str = Field(..., description="변경을 수행한 운영자.")


class AdminSystemPromptSchema(AdminBaseModel):
    channel: PromptChannel = Field(..., description="적용 채널(chat|rag|self_check).")
    prompt: str = Field(..., description="시스템 프롬프트 본문.")
    updatedAt: Optional[str] = Field(default=None, description="최근 변경 시각.")
    updatedBy: Optional[str] = Field(default=None, description="최근 변경을 수행한 운영자.")


class AdminSystemPromptListResponse(AdminBaseModel):
    items: List[AdminSystemPromptSchema] = Field(default_factory=list, description="시스템 프롬프트 목록.")


class AdminSystemPromptUpdateRequest(AdminBaseModel):
    channel: PromptChannel = Field(..., description="변경할 프롬프트 채널.")
    prompt: str = Field(..., description="새로운 시스템 프롬프트.")
    actor: str = Field(..., description="변경을 수행하는 운영자.")
    note: Optional[str] = Field(default=None, description="변경 이유 또는 메모.")


class AdminGuardrailPolicySchema(AdminBaseModel):
    intentRules: List[Dict[str, Any]] = Field(default_factory=list, description="의도 분류 규칙 목록.")
    blocklist: List[str] = Field(default_factory=list, description="차단어 또는 구문 목록.")
    userFacingCopy: Dict[str, str] = Field(default_factory=dict, description="사용자 안내 문구(친근한 톤).")


class AdminGuardrailPolicyResponse(AdminBaseModel):
    policy: AdminGuardrailPolicySchema = Field(..., description="Guardrail 정책 본문.")
    updatedAt: Optional[str] = Field(default=None, description="정책 수정 시각.")
    updatedBy: Optional[str] = Field(default=None, description="정책 수정 운영자.")


class AdminGuardrailPolicyUpdateRequest(AdminGuardrailPolicySchema):
    actor: str = Field(..., description="변경을 수행하는 운영자.")
    note: Optional[str] = Field(default=None, description="변경 메모.")


class AdminGuardrailEvaluateRequest(AdminBaseModel):
    sample: str = Field(..., description="평가할 프롬프트 또는 응답 샘플.")
    channels: Optional[List[str]] = Field(default=None, description="적용할 채널 목록. 미지정 시 기본 채널 사용.")


class AdminGuardrailDiffLineSchema(AdminBaseModel):
    kind: Literal["added", "removed", "same"] = Field(..., description="라인 diff 유형(+|-|=).")
    text: str = Field(..., description="라인 내용.")


class AdminGuardrailEvaluateResponse(AdminBaseModel):
    result: str = Field(..., description="평가 결괏값(summary|pass|fail 등).")
    details: Dict[str, Any] = Field(default_factory=dict, description="judge 모델 또는 규칙 기반 평가 상세.")
    loggedAt: str = Field(..., description="감사 로그에 기록된 시각(ISO8601).")
    auditFile: str = Field(..., description="감사 로그 파일명.")
    sampleId: Optional[str] = Field(default=None, description="저장된 평가 샘플 식별자.")
    lineDiff: List[AdminGuardrailDiffLineSchema] = Field(default_factory=list, description="라인 단위 diff 결과.")


class AdminGuardrailSampleSchema(AdminBaseModel):
    sampleId: str = Field(..., description="저장된 Guardrail 평가 샘플 ID.")
    result: str = Field(..., description="평가 결과(pass|blocked|warn 등).")
    channels: List[str] = Field(default_factory=list, description="적용된 채널 목록.")
    matchedRules: List[str] = Field(default_factory=list, description="매칭된 규칙 또는 블록리스트 항목.")
    judgeDecision: Optional[str] = Field(default=None, description="Judge 모델이 반환한 결정.")
    evaluatedAt: str = Field(..., description="평가 시각(ISO8601).")
    actor: str = Field(..., description="평가를 실행한 운영자.")
    bookmarked: bool = Field(default=False, description="북마크 여부.")
    sample: str = Field(..., description="평가 대상 원본 샘플.")
    sanitizedSample: str = Field(..., description="필요 시 정제된 샘플.")
    auditFile: Optional[str] = Field(default=None, description="연결된 감사 로그 파일명.")
    note: Optional[str] = Field(default=None, description="운영자 메모.")
    lineDiff: List[AdminGuardrailDiffLineSchema] = Field(default_factory=list, description="라인 단위 diff 결과.")


class AdminGuardrailSampleListResponse(AdminBaseModel):
    items: List[AdminGuardrailSampleSchema] = Field(default_factory=list, description="저장된 평가 샘플 목록.")
    hasMore: bool = Field(default=False, description="추가 페이지 존재 여부.")
    nextCursor: Optional[str] = Field(default=None, description="다음 페이지 조회용 커서.")


class AdminGuardrailBookmarkRequest(AdminBaseModel):
    bookmarked: bool = Field(..., description="설정할 북마크 상태.")


class AdminUiUxThemeSchema(AdminBaseModel):
    primaryColor: str = Field(..., description="브랜드 기본 색상 (hex).")
    accentColor: str = Field(..., description="강조 색상 (hex).")


class AdminUiUxDefaultsSchema(AdminBaseModel):
    dateRange: str = Field(..., description="대시보드 기본 기간(1D|1W|1M|3M|6M|1Y).")
    landingView: str = Field(..., description="첫 화면(default overview|alerts|evidence|operations).")


class AdminUiUxCopySchema(AdminBaseModel):
    welcomeHeadline: str = Field(..., description="대시보드 첫 인사 문구.")
    welcomeSubcopy: str = Field(..., description="보조 설명 문구.")
    quickCta: str = Field(..., description="빠른 실행 버튼 라벨.")


class AdminUiUxBannerSchema(AdminBaseModel):
    enabled: bool = Field(default=False, description="배너 활성화 여부.")
    message: str = Field(default="", description="배너 안내 문구.")
    linkLabel: Optional[str] = Field(default="", description="배너 링크 라벨.")
    linkUrl: Optional[str] = Field(default="", description="배너 링크 URL.")


class AdminUiUxSettingsSchema(AdminBaseModel):
    theme: AdminUiUxThemeSchema = Field(..., description="브랜드 색상 설정.")
    defaults: AdminUiUxDefaultsSchema = Field(..., description="대시보드 기본 동작 설정.")
    copy_block: AdminUiUxCopySchema = Field(
        ...,
        alias="copy",
        serialization_alias="copy",
        description="기본 문구 모음.",
    )
    banner: AdminUiUxBannerSchema = Field(..., description="상단 배너 설정.")

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)


class AdminUiUxSettingsResponse(AdminBaseModel):
    settings: AdminUiUxSettingsSchema = Field(..., description="현재 저장된 UI·UX 설정.")
    updatedAt: Optional[str] = Field(default=None, description="최근 변경 시각.")
    updatedBy: Optional[str] = Field(default=None, description="최근 변경 운영자.")


class AdminUiUxSettingsUpdateRequest(AdminBaseModel):
    settings: AdminUiUxSettingsSchema = Field(..., description="저장할 UI·UX 설정 값.")
    actor: str = Field(..., description="변경을 수행하는 운영자.")
    note: Optional[str] = Field(default=None, description="변경 사유 메모.")


class AdminRagSourceSchema(AdminBaseModel):
    key: str = Field(..., description="소스 식별자.")
    name: str = Field(..., description="소스 표시 이름.")
    enabled: bool = Field(default=True, description="활성화 여부.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="소스 관련 부가 정보.")


class AdminRagFilterSchema(AdminBaseModel):
    field: str = Field(..., description="필터 대상 필드.")
    operator: str = Field(..., description="적용 연산자(eq, in, gte 등).")
    value: Any = Field(..., description="필터 비교 값.")


class AdminRagConfigSchema(AdminBaseModel):
    sources: List[AdminRagSourceSchema] = Field(default_factory=list, description="활성화된 컨텍스트 소스.")
    filters: List[AdminRagFilterSchema] = Field(default_factory=list, description="기본 적용 필터.")
    similarityThreshold: float = Field(..., ge=0.0, le=1.0, description="유사도 컷오프(0~1).")
    rerankModel: Optional[str] = Field(default=None, description="재순위 모델 ID.")
    updatedAt: Optional[str] = Field(default=None, description="최근 설정 변경 시각.")
    updatedBy: Optional[str] = Field(default=None, description="최근 설정 변경 운영자.")


class AdminRagConfigResponse(AdminBaseModel):
    config: AdminRagConfigSchema = Field(..., description="현재 적용된 RAG 설정.")


class AdminRagConfigUpdateRequest(AdminRagConfigSchema):
    actor: str = Field(..., description="변경을 수행하는 운영자.")
    note: Optional[str] = Field(default=None, description="변경 사유.")


class AdminRagReindexRequest(AdminBaseModel):
    sources: Optional[List[str]] = Field(default=None, description="재색인할 소스 키 목록. 없으면 전체.")
    refreshFilters: bool = Field(default=False, description="필터 스냅샷을 갱신할지 여부.")
    actor: str = Field(..., description="요청 운영자.")
    note: Optional[str] = Field(default=None, description="요청 메모.")


class AdminRagReindexResponse(AdminBaseModel):
    taskId: str = Field(..., description="재색인 작업 ID.")
    status: str = Field(..., description="재색인 상태(queued|running|completed|failed).")


class AdminRagEvidenceFieldDiffSchema(AdminBaseModel):
    field: str = Field(..., description="비교한 필드 이름.")
    before: Optional[str] = Field(default=None, description="변경 전 값.")
    after: Optional[str] = Field(default=None, description="변경 후 값.")
    lineDiff: List[str] = Field(default_factory=list, description="라인 단위 diff 결과(+- 기호 포함).")

class AdminRagPdfRectSchema(AdminBaseModel):
    page: Optional[int] = Field(default=None, ge=1, description="PDF 1-based 페이지 인덱스.")
    x: Optional[float] = Field(default=None, ge=0, description="하이라이트 X 좌표(포인트 단위).")
    y: Optional[float] = Field(default=None, ge=0, description="하이라이트 Y 좌표(포인트 단위).")
    width: Optional[float] = Field(default=None, ge=0, description="하이라이트 영역 너비.")
    height: Optional[float] = Field(default=None, ge=0, description="하이라이트 영역 높이.")


class AdminRagEvidenceAnchorSchema(AdminBaseModel):
    paragraphId: Optional[str] = Field(default=None, description="문단 식별자.")
    pdfRect: Optional[AdminRagPdfRectSchema] = Field(default=None, description="PDF 하이라이트 좌표.")
    similarity: Optional[float] = Field(default=None, ge=0, le=1, description="검색 유사도 점수.")


class AdminRagEvidenceSelfCheckSchema(AdminBaseModel):
    score: Optional[float] = Field(default=None, ge=0, le=1, description="자체 검증 신뢰도 점수.")
    verdict: Optional[Literal["pass", "warn", "fail"]] = Field(default=None, description="판정 결과.")
    explanation: Optional[str] = Field(default=None, description="추가 설명.")


class AdminRagEvidenceDiffItemSchema(AdminBaseModel):
    urnId: Optional[str] = Field(default=None, description="변경된 Evidence의 URN ID.")
    diffType: str = Field(..., description="변경 유형(created|updated|removed|unchanged).")
    source: Optional[str] = Field(default=None, description="Evidence가 속한 소스.")
    section: Optional[str] = Field(default=None, description="원문 섹션.")
    quote: Optional[str] = Field(default=None, description="주요 인용문 요약.")
    chunkId: Optional[str] = Field(default=None, description="벡터 청크 ID.")
    updatedAt: Optional[str] = Field(default=None, description="스냅샷이 저장된 시각.")
    pageNumber: Optional[int] = Field(default=None, ge=1, description="현재 Evidence가 위치한 PDF 페이지 번호.")
    previousPageNumber: Optional[int] = Field(default=None, ge=1, description="이전 Evidence 페이지 번호.")
    anchor: Optional[AdminRagEvidenceAnchorSchema] = Field(default=None, description="현재 하이라이트 좌표.")
    previousAnchor: Optional[AdminRagEvidenceAnchorSchema] = Field(default=None, description="이전 하이라이트 좌표.")
    selfCheck: Optional[AdminRagEvidenceSelfCheckSchema] = Field(default=None, description="현재 Self Check 결과.")
    previousSelfCheck: Optional[AdminRagEvidenceSelfCheckSchema] = Field(
        default=None, description="이전 Self Check 결과."
    )
    sourceReliability: Optional[Literal["high", "medium", "low"]] = Field(
        default=None, description="현재 Evidence의 출처 신뢰도."
    )
    previousSourceReliability: Optional[Literal["high", "medium", "low"]] = Field(
        default=None, description="이전 Evidence 출처 신뢰도."
    )
    documentUrl: Optional[str] = Field(default=None, description="원문 문서를 열 수 있는 기본 URL.")
    viewerUrl: Optional[str] = Field(default=None, description="문서 뷰어 URL.")
    downloadUrl: Optional[str] = Field(default=None, description="문서를 직접 다운로드할 수 있는 URL.")
    sourceUrl: Optional[str] = Field(default=None, description="원본 출처 URL.")
    langfuseTraceUrl: Optional[str] = Field(default=None, description="Langfuse trace 링크.")
    langfuseTraceId: Optional[str] = Field(default=None, description="Langfuse trace ID.")
    langfuseSpanId: Optional[str] = Field(default=None, description="Langfuse span ID.")
    diffChangedFields: Optional[List[str]] = Field(default=None, description="변경된 필드 목록.")
    changes: List[AdminRagEvidenceFieldDiffSchema] = Field(default_factory=list, description="필드별 변경 요약.")


class AdminRagEvidenceDiffSchema(AdminBaseModel):
    totalChanges: int = Field(..., description="감지된 전체 변화 수.")
    created: int = Field(..., description="신규 Evidence 수.")
    updated: int = Field(..., description="내용이 갱신된 Evidence 수.")
    removed: int = Field(..., description="제거된 Evidence 수.")
    samples: List[AdminRagEvidenceDiffItemSchema] = Field(default_factory=list, description="변경 샘플 목록.")


class AdminRagReindexRecordSchema(AdminBaseModel):
    taskId: str = Field(..., description="재색인 작업 ID.")
    actor: str = Field(..., description="재색인을 요청한 운영자.")
    scope: str = Field(..., description="재색인 대상 소스 목록(콤마 구분).")
    status: str = Field(..., description="재색인 상태(queued|running|completed|failed|retrying|partial).")
    note: Optional[str] = Field(default=None, description="재색인 메모.")
    timestamp: str = Field(..., description="로그가 기록된 시각(ISO8601).")
    startedAt: Optional[str] = Field(default=None, description="재색인이 실제로 시작된 시각(ISO8601).")
    finishedAt: Optional[str] = Field(default=None, description="재색인이 종료된 시각(ISO8601).")
    durationMs: Optional[int] = Field(default=None, description="재색인 처리에 걸린 시간(ms).")
    errorCode: Optional[str] = Field(default=None, description="실패 시 에러 코드.")
    langfuseTraceUrl: Optional[str] = Field(default=None, description="Langfuse trace 바로가기 URL.")
    langfuseTraceId: Optional[str] = Field(default=None, description="Langfuse trace 식별자.")
    langfuseSpanId: Optional[str] = Field(default=None, description="Langfuse span 식별자.")
    queueId: Optional[str] = Field(default=None, description="재시도 큐와 연결된 경우 해당 queue ID.")
    evidenceDiff: Optional[AdminRagEvidenceDiffSchema] = Field(default=None, description="재색인으로 발생한 Evidence 변화 요약.")
    retryMode: Optional[str] = Field(default=None, description="재시도 방식(auto|manual).")
    ragMode: Optional[str] = Field(default=None, description="Judge가 판정한 rag_mode 값.")
    scopeDetail: Optional[List[str]] = Field(default=None, description="정규화된 재색인 소스 목록.")
    queuedAt: Optional[str] = Field(default=None, description="대기열에 등록된 시각(ISO8601).")
    queueWaitMs: Optional[int] = Field(default=None, description="대기열에서 실제 실행당에 걸린 시간(ms).")
    totalElapsedMs: Optional[int] = Field(default=None, description="대기 반영 후 종료까지 소요된 총 시간(ms).")
    eventBriefPath: Optional[str] = Field(default=None, description="생성된 이벤트 브리프 PDF의 로컬 경로.")
    eventBriefObject: Optional[str] = Field(default=None, description="이벤트 브리프 PDF가 업로드된 MinIO 객체 키.")
    eventBriefUrl: Optional[str] = Field(default=None, description="이벤트 브리프 PDF presigned URL.")
    evidencePackagePath: Optional[str] = Field(default=None, description="증거 패키지 ZIP 로컬 경로.")
    evidencePackageObject: Optional[str] = Field(default=None, description="증거 패키지 ZIP MinIO 객체 키.")
    evidencePackageUrl: Optional[str] = Field(default=None, description="증거 패키지 ZIP presigned URL.")
    evidenceManifestPath: Optional[str] = Field(default=None, description="패키지 manifest JSON 로컬 경로.")


class AdminRagReindexHistorySummary(AdminBaseModel):
    totalRuns: int = Field(..., description="집계된 전체 재색인 실행 횟수.")
    completed: int = Field(..., description="완료된 실행 수.")
    failed: int = Field(..., description="실패한 실행 수.")
    traced: int = Field(..., description="Langfuse trace가 연결된 실행 수.")
    missingTraces: int = Field(..., description="Langfuse trace가 누락된 실행 수.")
    averageDurationMs: Optional[int] = Field(default=None, description="평균 처리 시간(ms).")
    latestTraceUrls: List[str] = Field(default_factory=list, description="최신 Langfuse trace URL 목록.")
    modeUsage: Dict[str, int] = Field(default_factory=dict, description="rag_mode별 실행 횟수.")
    lastRunAt: Optional[str] = Field(default=None, description="가장 최근 실행 시각.")
    p50DurationMs: Optional[int] = Field(default=None, description="전체 처리 시간 중 50번째 백분위(ms).")
    p95DurationMs: Optional[int] = Field(default=None, description="전체 처리 시간 중 95번째 백분위(ms).")
    p50QueueWaitMs: Optional[int] = Field(default=None, description="대기 시간 중 50번째 백분위(ms).")
    p95QueueWaitMs: Optional[int] = Field(default=None, description="대기 시간 중 95번째 백분위(ms).")
    slaTargetMs: int = Field(..., description="SLA 목표 시간(ms).")
    slaBreaches: int = Field(..., description="SLA를 초과한 실행 횟수.")
    slaMet: int = Field(..., description="SLA를 충족한 실행 횟수.")


class AdminRagReindexHistoryResponse(AdminBaseModel):
    runs: List[AdminRagReindexRecordSchema] = Field(default_factory=list, description="최근 재색인 실행 이력.")
    summary: Optional[AdminRagReindexHistorySummary] = Field(default=None, description="Langfuse 및 실행 현황 요약.")


class AdminRagReindexQueueSummary(AdminBaseModel):
    totalEntries: int = Field(..., description="큐에 남아 있는 전체 항목 수.")
    ready: int = Field(..., description="즉시 실행 가능한 항목 수.")
    coolingDown: int = Field(..., description="자동 재시도 대기 중인 항목 수.")
    autoMode: int = Field(..., description="자동 재시도 모드 항목 수.")
    manualMode: int = Field(..., description="수동 재시도 모드 항목 수.")
    nextAutoRetryAt: Optional[str] = Field(default=None, description="다음 자동 재시도 예정 시각.")
    stalled: int = Field(..., description="재시도 제한에 도달한 항목 수.")
    oldestQueuedMs: Optional[int] = Field(default=None, description="가장 오래된 큐 항목의 누적 대기 시간(ms).")
    averageCooldownRemainingMs: Optional[int] = Field(default=None, description="쿨다운 중인 항목의 평균 남은 시간(ms).")
    slaRiskCount: int = Field(..., description="SLA 초과 위험이 있는 큐 항목 수.")


class AdminRagReindexQueueEntrySchema(AdminBaseModel):
    queueId: str = Field(..., description="재시도 큐 항목 ID.")
    originalTaskId: str = Field(..., description="실패한 원본 재색인 작업 ID.")
    scope: str = Field(..., description="재색인 대상 소스 목록(콤마 구분).")
    actor: str = Field(..., description="최초 실패 시점의 운영자.")
    note: Optional[str] = Field(default=None, description="재시도 메모.")
    status: str = Field(..., description="큐 상태(queued|running|failed|completed).")
    attempts: int = Field(..., ge=0, description="재시도 횟수.")
    lastError: Optional[str] = Field(default=None, description="가장 최근 오류 메시지.")
    lastTaskId: Optional[str] = Field(default=None, description="마지막으로 생성된 재색인 작업 ID.")
    lastAttemptAt: Optional[str] = Field(default=None, description="최근 재시도 시각.")
    lastSuccessAt: Optional[str] = Field(default=None, description="마지막 성공 시각.")
    langfuseTraceUrl: Optional[str] = Field(default=None, description="Langfuse trace URL.")
    langfuseTraceId: Optional[str] = Field(default=None, description="Langfuse trace ID.")
    langfuseSpanId: Optional[str] = Field(default=None, description="Langfuse span ID.")
    createdAt: str = Field(..., description="큐 항목 생성 시각.")
    updatedAt: str = Field(..., description="마지막 업데이트 시각.")
    retryMode: Optional[str] = Field(default=None, description="자동 또는 수동 재시도 식별자.")
    cooldownUntil: Optional[str] = Field(default=None, description="자동 재시도 대기 종료 시각(ISO8601).")
    maxAttempts: Optional[int] = Field(default=None, description="자동 재시도 최대 허용 횟수.")
    queueAgeMs: Optional[int] = Field(default=None, description="현재까지 누적 대기 시간(ms).")
    cooldownRemainingMs: Optional[int] = Field(default=None, description="남아 있는 쿨다운 시간(ms).")
    slaBreached: bool = Field(default=False, description="SLA 목표를 초과했는지 여부.")


class AdminRagReindexQueueResponse(AdminBaseModel):
    entries: List[AdminRagReindexQueueEntrySchema] = Field(default_factory=list, description="재시도 큐 목록.")
    summary: Optional[AdminRagReindexQueueSummary] = Field(default=None, description="자동 재시도 흐름 요약.")


class AdminRagSlaSummary(AdminBaseModel):
    totalRuns: int = Field(..., description="선택한 기간 동안 수행된 총 재색인 횟수.")
    completedRuns: int = Field(..., description="성공한 재색인 횟수.")
    failedRuns: int = Field(..., description="실패한 재색인 횟수.")
    slaBreaches: int = Field(..., description="SLA(30분)를 초과한 횟수.")
    slaBreachRatio: float = Field(..., description="전체 대비 SLA 초과 비율.")
    p50TotalMs: Optional[int] = Field(default=None, description="총 소요시간 p50 (ms).")
    p95TotalMs: Optional[int] = Field(default=None, description="총 소요시간 p95 (ms).")
    p50QueueMs: Optional[int] = Field(default=None, description="큐 대기시간 p50 (ms).")
    p95QueueMs: Optional[int] = Field(default=None, description="큐 대기시간 p95 (ms).")


class AdminRagSlaTimeseriesPoint(AdminBaseModel):
    day: str = Field(..., description="일자 (UTC).")
    totalRuns: int = Field(..., description="해당 일자의 재색인 횟수.")
    slaBreaches: int = Field(..., description="해당 일자의 SLA 초과 건수.")
    slaBreachRatio: float = Field(..., description="해당 일자의 SLA 초과 비율.")
    p50TotalMs: Optional[int] = Field(default=None, description="총 소요시간 p50 (ms).")
    p95TotalMs: Optional[int] = Field(default=None, description="총 소요시간 p95 (ms).")


class AdminRagSlaViolation(AdminBaseModel):
    timestamp: Optional[str] = Field(default=None, description="재색인 완료 시각.")
    actor: Optional[str] = Field(default=None, description="실행 주체.")
    scope: Optional[str] = Field(default=None, description="재색인 적용 범위.")
    scopeDetail: Optional[List[str]] = Field(default=None, description="재색인 대상 상세.")
    note: Optional[str] = Field(default=None, description="운영자가 남긴 메모.")
    status: Optional[str] = Field(default=None, description="최종 상태.")
    retryMode: Optional[str] = Field(default=None, description="재시도 모드.")
    ragMode: Optional[str] = Field(default=None, description="RAG 모드.")
    queueId: Optional[str] = Field(default=None, description="큐 항목 ID.")
    queueWaitMs: Optional[int] = Field(default=None, description="큐 대기시간 (ms).")
    totalElapsedMs: Optional[int] = Field(default=None, description="총 소요시간 (ms).")
    langfuseTraceUrl: Optional[str] = Field(default=None, description="Langfuse Trace URL.")
    langfuseTraceId: Optional[str] = Field(default=None, description="Langfuse Trace ID.")
    langfuseSpanId: Optional[str] = Field(default=None, description="Langfuse Span ID.")


class AdminRagSlaResponse(AdminBaseModel):
    generatedAt: str = Field(..., description="데이터 생성 시각 (UTC).")
    rangeDays: int = Field(..., description="집계 기준 기간(일).")
    slaTargetMinutes: int = Field(..., description="SLA 목표 시간(분).")
    slaTargetMs: int = Field(..., description="SLA 목표 시간(ms).")
    summary: AdminRagSlaSummary = Field(..., description="요약 통계.")
    timeseries: List[AdminRagSlaTimeseriesPoint] = Field(default_factory=list, description="일자별 추세.")
    recentViolations: List[AdminRagSlaViolation] = Field(default_factory=list, description="최근 SLA 초과 사례.")


class AdminRagReindexRetryRequest(AdminBaseModel):
    queueId: str = Field(..., description="재시도할 큐 항목 ID.")
    actor: str = Field(..., description="재시도를 실행한 운영자.")
    note: Optional[str] = Field(default=None, description="재시도 메모(선택). 지정 시 기존 메모를 덮어씁니다.")
    sources: Optional[List[str]] = Field(default=None, description="재색인 대상 소스를 명시적으로 지정할 경우 사용합니다.")


class AdminRagReindexRetryResponse(AdminBaseModel):
    queueId: str = Field(..., description="재시도한 큐 항목 ID.")
    taskId: Optional[str] = Field(default=None, description="재시도로 생성된 재색인 작업 ID.")
    status: str = Field(..., description="재시도 요청 결과 상태.")


class AdminOpsScheduleSchema(AdminBaseModel):
    id: str = Field(..., description="스케줄 식별자.")
    task: str = Field(..., description="Celery 태스크 dotted path.")
    interval: str = Field(..., description="실행 주기 표현(예: cron, every 5m).")
    status: Literal["active", "paused"] = Field(..., description="활성/중지 상태.")
    nextRunAt: Optional[str] = Field(default=None, description="다음 실행 예정 시각.")


class AdminOpsScheduleListResponse(AdminBaseModel):
    jobs: List[AdminOpsScheduleSchema] = Field(default_factory=list, description="등록된 스케줄 목록.")


class AdminOpsTriggerRequest(AdminBaseModel):
    actor: str = Field(..., description="실행을 트리거한 운영자.")
    note: Optional[str] = Field(default=None, description="실행 메모.")


class AdminOpsTriggerResponse(AdminBaseModel):
    jobId: str = Field(..., description="트리거된 스케줄 ID.")
    taskId: str = Field(..., description="실제 실행된 작업 ID.")
    status: str = Field(..., description="실행 상태(queued|running).")


class AdminAlertPresetUsageEntry(AdminBaseModel):
    presetId: str = Field(..., description="프리셋 식별자.")
    bundle: Optional[str] = Field(default=None, description="소속된 번들 이름.")
    count: int = Field(..., description="집계 기간 동안 생성된 횟수.")
    lastUsedAt: Optional[datetime] = Field(default=None, description="가장 최근 실행 시각.")
    channelTotals: Dict[str, int] = Field(default_factory=dict, description="채널별 생성 횟수.")


class AdminAlertPresetBundleUsage(AdminBaseModel):
    bundle: str = Field(..., description="번들 식별자.")
    count: int = Field(..., description="집계 기간 동안의 총 실행 횟수.")


class AdminAlertPresetUsageResponse(AdminBaseModel):
    generatedAt: datetime = Field(..., description="데이터 생성 시각.")
    windowDays: int = Field(..., description="집계 기간(일).")
    totalLaunches: int = Field(..., description="전체 프리셋 생성 횟수.")
    presets: List[AdminAlertPresetUsageEntry] = Field(default_factory=list, description="프리셋별 사용량.")
    bundles: List[AdminAlertPresetBundleUsage] = Field(default_factory=list, description="번들별 사용량.")
    planTotals: Dict[str, int] = Field(default_factory=dict, description="플랜 티어별 프리셋 생성 횟수.")


QuickActionName = Literal["seed-news", "aggregate-sentiment", "rebuild-rag"]


class AdminOpsQuickActionRequest(AdminBaseModel):
    actor: str = Field(..., description="실행을 요청한 운영자.")
    note: Optional[str] = Field(default=None, description="실행 메모 또는 비고.")


class AdminOpsQuickActionResponse(AdminBaseModel):
    action: QuickActionName = Field(..., description="실행된 퀵 액션 식별자.")
    status: str = Field(..., description="실행 상태(queued|running 등).")
    taskId: Optional[str] = Field(default=None, description="백그라운드 작업 ID(해당되는 경우).")
    message: Optional[str] = Field(default=None, description="사용자에게 표시할 추가 메시지.")


class AdminOpsNewsPipelineSchema(AdminBaseModel):
    rssFeeds: List[str] = Field(default_factory=list, description="추적할 RSS/뉴스 피드 URL 목록.")
    sectorMappings: Dict[str, List[str]] = Field(default_factory=dict, description="섹터별 키워드 매핑.")
    sentiment: Dict[str, Any] = Field(default_factory=dict, description="감성 분석 임계값 등 메타 설정.")


class AdminOpsNewsPipelineResponse(AdminBaseModel):
    pipeline: AdminOpsNewsPipelineSchema = Field(..., description="뉴스 파이프라인 설정.")
    updatedAt: Optional[str] = Field(default=None, description="최근 변경 시각.")
    updatedBy: Optional[str] = Field(default=None, description="변경 운영자.")


class AdminOpsNewsPipelineUpdateRequest(AdminOpsNewsPipelineSchema):
    actor: str = Field(..., description="변경 운영자.")
    note: Optional[str] = Field(default=None, description="변경 메모.")


class AdminOpsApiKeyRotationSchema(AdminBaseModel):
    rotatedAt: str = Field(..., description="키가 회전된 시각(ISO8601).")
    actor: str = Field(..., description="회전을 수행한 운영자.")
    note: Optional[str] = Field(default=None, description="회전 사유 또는 메모.")
    maskedKey: Optional[str] = Field(default=None, description="회전 시점의 마스킹된 키.")


class AdminOpsApiKeySchema(AdminBaseModel):
    name: str = Field(..., description="외부 API 이름.")
    maskedKey: Optional[str] = Field(default=None, description="마스킹된 키 표시.")
    enabled: bool = Field(default=True, description="사용 여부.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터.")
    expiresAt: Optional[str] = Field(default=None, description="키 만료 예정 시각(ISO8601).")
    warningThresholdDays: Optional[int] = Field(default=None, description="만료 임박 안내를 표시할 일수.")
    lastRotatedAt: Optional[str] = Field(default=None, description="최근 회전 시각(ISO8601).")
    rotationHistory: List[AdminOpsApiKeyRotationSchema] = Field(
        default_factory=list,
        description="회전 이력 기록(최신 순).",
    )


class AdminOpsLangfuseEnvironmentSchema(AdminBaseModel):
    name: str = Field(..., description="환경 이름(예: production, staging).")
    enabled: bool = Field(default=True, description="환경 활성화 여부.")
    host: Optional[str] = Field(default=None, description="Langfuse 호스트 URL.")
    publicKey: Optional[str] = Field(default=None, description="노출 가능한 Public Key.")
    maskedPublicKey: Optional[str] = Field(default=None, description="마스킹된 Public Key.")
    secretKey: Optional[str] = Field(default=None, description="실제 Secret Key.")
    maskedSecretKey: Optional[str] = Field(default=None, description="마스킹된 Secret Key.")
    expiresAt: Optional[str] = Field(default=None, description="만료 예정 시각(ISO8601).")
    warningThresholdDays: Optional[int] = Field(default=None, description="만료 경고 임계값(일 단위).")
    lastRotatedAt: Optional[str] = Field(default=None, description="최근 회전 시각(ISO8601).")
    rotationHistory: List[AdminOpsApiKeyRotationSchema] = Field(default_factory=list, description="환경별 회전 이력.")
    note: Optional[str] = Field(default=None, description="환경 관련 메모.")


class AdminOpsLangfuseConfigSchema(AdminBaseModel):
    defaultEnvironment: str = Field(..., description="기본 선택 환경.")
    environments: List[AdminOpsLangfuseEnvironmentSchema] = Field(default_factory=list, description="등록된 환경 목록.")


class AdminOpsApiKeyCollection(AdminBaseModel):
    langfuse: AdminOpsLangfuseConfigSchema = Field(..., description="Langfuse 토큰/키 정보(다중 환경).")
    externalApis: List[AdminOpsApiKeySchema] = Field(default_factory=list, description="기타 외부 API 목록.")


class AdminOpsTokenAlertSchema(AdminBaseModel):
    source: str = Field(..., description="알림 출처(예: langfuse:production).")
    severity: Literal["info", "warning", "critical"] = Field(..., description="알림 심각도.")
    message: str = Field(..., description="요약 메시지.")
    detail: Optional[str] = Field(default=None, description="추가 설명.")


class AdminOpsApiKeyResponse(AdminBaseModel):
    secrets: AdminOpsApiKeyCollection = Field(..., description="운영 API 키 설정.")
    updatedAt: Optional[str] = Field(default=None, description="최근 변경 시각.")
    updatedBy: Optional[str] = Field(default=None, description="변경 운영자.")
    alerts: List[AdminOpsTokenAlertSchema] = Field(default_factory=list, description="토큰/세션 만료 안내.")


class AdminOpsApiKeyUpdateRequest(AdminOpsApiKeyCollection):
    actor: str = Field(..., description="변경 운영자.")
    note: Optional[str] = Field(default=None, description="변경 메모.")


class AdminOpsAlertChannelSchema(AdminBaseModel):
    key: str = Field(..., min_length=1, max_length=120, description="채널 고유 키.")
    label: str = Field(..., min_length=1, max_length=200, description="운영자가 구분하기 위한 채널 이름.")
    channelType: str = Field(..., min_length=1, max_length=50, description="알림 채널 종류(telegram, email 등).")
    enabled: bool = Field(default=True, description="활성화 여부.")
    targets: List[str] = Field(default_factory=list, description="기본 발송 대상 목록.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="채널 전용 메타데이터.")
    template: Optional[str] = Field(default=None, description="사전 정의된 템플릿 키.")
    messageTemplate: Optional[str] = Field(default=None, description="기본 메시지 템플릿(옵션).")
    description: Optional[str] = Field(default=None, description="채널 설명 또는 메모.")
    createdAt: Optional[str] = Field(default=None, description="채널이 생성된 시각(ISO8601).")
    updatedAt: Optional[str] = Field(default=None, description="최근 수정 시각(ISO8601).")
    disabledAt: Optional[str] = Field(default=None, description="비활성화된 시각(ISO8601).")
    disabledBy: Optional[str] = Field(default=None, description="채널을 비활성화한 운영자.")
    disabledNote: Optional[str] = Field(default=None, description="비활성화 사유.")

    @field_validator("targets", mode="before")
    def _normalize_targets(cls, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            candidates = value.replace("\r", "\n").split("\n")
        elif isinstance(value, (list, tuple, set)):
            candidates = list(value)
        else:
            return []
        result: List[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = str(candidate).strip()
            if not text or text in seen:
                continue
            result.append(text)
            seen.add(text)
        return result

    @field_validator("metadata", mode="before")
    def _ensure_metadata(cls, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        sanitized: Dict[str, Any] = {}
        for key, entry in value.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            sanitized[key_str] = entry
        return sanitized


class AdminOpsAlertChannelResponse(AdminBaseModel):
    channels: List[AdminOpsAlertChannelSchema] = Field(default_factory=list, description="등록된 알림 채널 목록.")
    updatedAt: Optional[str] = Field(default=None, description="최근 변경 시각.")
    updatedBy: Optional[str] = Field(default=None, description="최근 변경 운영자.")
    note: Optional[str] = Field(default=None, description="최근 변경 메모.")


class AdminOpsAlertChannelUpdateRequest(AdminBaseModel):
    channels: List[AdminOpsAlertChannelSchema] = Field(default_factory=list, description="저장할 알림 채널 목록.")
    actor: str = Field(..., description="변경 운영자.")
    note: Optional[str] = Field(default=None, description="변경 메모.")


class AdminOpsAlertChannelCreateRequest(AdminBaseModel):
    channelType: str = Field(..., min_length=1, max_length=50, description="생성할 채널 종류.")
    label: str = Field(..., min_length=1, max_length=200, description="채널 표시 이름.")
    targets: List[str] = Field(default_factory=list, description="기본 발송 대상.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터.")
    template: Optional[str] = Field(default=None, description="템플릿 키.")
    messageTemplate: Optional[str] = Field(default=None, description="메시지 템플릿.")
    description: Optional[str] = Field(default=None, description="채널 설명.")
    actor: str = Field(..., description="생성 운영자.")
    note: Optional[str] = Field(default=None, description="생성 메모.")


class AdminOpsAlertChannelStatusUpdateRequest(AdminBaseModel):
    enabled: bool = Field(..., description="변경할 활성화 상태.")
    note: Optional[str] = Field(default=None, description="상태 변경 메모.")
    actor: str = Field(..., description="상태 변경 운영자.")


class AdminOpsAlertChannelPreviewRequest(AdminBaseModel):
    channel: AdminOpsAlertChannelSchema = Field(..., description="렌더링할 채널 설정.")
    sampleMessage: str = Field(..., description="미리보기용 메시지 문구.")
    sampleMetadata: Dict[str, Any] = Field(default_factory=dict, description="템플릿에 주입할 메타데이터.")
    actor: str = Field(..., description="미리보기를 수행하는 운영자.")


class AdminOpsAlertChannelPreviewResponse(AdminBaseModel):
    rendered: Dict[str, Any] = Field(default_factory=dict, description="미리보기로 생성된 메시지 페이로드.")
    message: str = Field(..., description="템플릿 적용 후 메시지 본문.")
    generatedAt: str = Field(..., description="미리보기 생성 시각(ISO8601).")
    templateUsed: Optional[str] = Field(default=None, description="적용된 템플릿 식별자.")
    actor: str = Field(..., description="미리보기를 실행한 운영자.")


class AdminOpsTemplateSchema(AdminBaseModel):
    key: str = Field(..., description="템플릿 고유 키.")
    label: str = Field(..., description="템플릿 표시 이름.")
    channelType: str = Field(..., description="적용 가능한 채널 유형.")
    template: Optional[str] = Field(default=None, description="템플릿 식별자 또는 형식.")
    messageTemplate: Optional[str] = Field(default=None, description="메시지 텍스트 템플릿.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="기본 제공 메타데이터.")
    description: Optional[str] = Field(default=None, description="템플릿 설명.")


class AdminOpsTemplateListResponse(AdminBaseModel):
    templates: List[AdminOpsTemplateSchema] = Field(default_factory=list, description="사용 가능한 템플릿 목록.")


class AdminOpsSampleMetadataRequest(AdminBaseModel):
    channelType: str = Field(..., description="샘플 메타데이터를 생성할 채널 유형.")
    template: Optional[str] = Field(default=None, description="선택적으로 적용할 템플릿 키.")


class AdminOpsSampleMetadataResponse(AdminBaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict, description="자동 생성된 샘플 메타데이터.")
    generatedAt: str = Field(..., description="생성 시각(ISO8601).")


class AdminAuditLogEntrySchema(AdminBaseModel):
    timestamp: str = Field(..., description="이벤트 발생 시각(ISO8601).")
    actor: str = Field(..., description="변경 주체.")
    action: str = Field(..., description="실행된 작업 코드.")
    source: str = Field(..., description="로그가 기록된 감사 파일 이름.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터.")


class AdminAuditLogListResponse(AdminBaseModel):
    items: List[AdminAuditLogEntrySchema] = Field(default_factory=list, description="감사 로그 목록.")
    hasMore: bool = Field(default=False, description="추가 로그가 더 존재하는지 여부.")
    nextCursor: Optional[str] = Field(default=None, description="다음 페이지 조회용 커서.")


class AdminOpsRunRecordSchema(AdminBaseModel):
    id: str = Field(..., description="실행 로그 ID.")
    jobId: Optional[str] = Field(default=None, description="예약 실행이 연계된 경우 Celery 잡 ID.")
    task: str = Field(..., description="실행된 태스크.")
    status: str = Field(..., description="실행 상태.")
    startedAt: str = Field(..., description="시작 시각.")
    finishedAt: Optional[str] = Field(default=None, description="종료 시각.")
    actor: Optional[str] = Field(default=None, description="실행을 요청한 운영자.")
    note: Optional[str] = Field(default=None, description="비고.")


class AdminOpsRunHistoryResponse(AdminBaseModel):
    runs: List[AdminOpsRunRecordSchema] = Field(default_factory=list, description="최근 실행 기록 목록.")


class WebhookAuditEntrySchema(AdminBaseModel):
    loggedAt: Optional[str] = Field(default=None, description="감사 로그가 기록된 시각 (UTC).")
    result: str = Field(..., description="처리 결과 식별자.")
    message: Optional[str] = Field(default=None, description="추가 설명 또는 오류 메시지.")
    context: Dict[str, Any] = Field(default_factory=dict, description="웹훅 처리 메타데이터.")
    payload: Optional[Dict[str, Any]] = Field(default=None, description="웹훅 원본 페이로드.")


class WebhookAuditListResponse(AdminBaseModel):
    items: List[WebhookAuditEntrySchema] = Field(default_factory=list, description="웹훅 감사 로그 목록.")


class PlanQuickAdjustQuota(AdminBaseModel):
    chatRequestsPerDay: Optional[int] = Field(default=None)
    ragTopK: Optional[int] = Field(default=None)
    selfCheckEnabled: Optional[bool] = Field(default=None)
    peerExportRowLimit: Optional[int] = Field(default=None)


class PlanQuickAdjustRequest(AdminBaseModel):
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
    memoryFlags: Optional[PlanMemoryFlagsSchema] = Field(
        default=None,
        description="LightMem 기능 토글을 조정할 때 사용합니다.",
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


class TossWebhookReplayRequest(AdminBaseModel):
    transmissionId: str = Field(..., description="재처리할 Toss webhook transmission ID.")


class TossWebhookReplayResponse(AdminBaseModel):
    status: str = Field(..., description="웹훅 이벤트 상태 값.")
    orderId: Optional[str] = Field(default=None, description="연관된 orderId.")
    tier: Optional[PlanTier] = Field(default=None, description="재처리로 적용된 플랜 티어.")
    noop: Optional[bool] = Field(default=None, description="실행할 작업이 없어 건너뛴 경우 true.")


class AdminSessionCreateRequest(AdminBaseModel):
    token: Optional[str] = Field(default=None, description="정적 운영 토큰.")
    idToken: Optional[str] = Field(default=None, description="Google Workspace ID 토큰.")
    actorOverride: Optional[str] = Field(default=None, description="(정적 토큰 전용) actor 라벨을 덮어쓸 때 사용합니다.")

    @model_validator(mode="after")
    def validate_credentials(cls, values: "AdminSessionCreateRequest") -> "AdminSessionCreateRequest":
        if not values.token and not values.idToken:
            raise ValueError("token 또는 idToken 중 하나는 반드시 필요합니다.")
        return values


class AdminSessionResponse(AdminBaseModel):
    actor: str = Field(..., description="Administrative actor label.")
    issuedAt: str = Field(..., description="ISO8601 timestamp when the session was issued.")
    tokenHint: Optional[str] = Field(default=None, description="Masked credential or session hint.")
    sessionId: Optional[str] = Field(default=None, description="Server-managed admin session ID.")
    expiresAt: Optional[str] = Field(default=None, description="ISO8601 expiration timestamp, if tracked.")


class AdminSessionRevokeResponse(AdminBaseModel):
    revoked: bool = Field(..., description="Whether the session was revoked in this call.")


class AdminCredentialLoginRequest(AdminBaseModel):
    email: str = Field(..., description="운영자 계정 이메일.")
    password: str = Field(..., description="운영자 비밀번호.")
    otp: Optional[str] = Field(default=None, description="TOTP 또는 일회용 MFA 코드.")


class AdminSsoProviderSchema(AdminBaseModel):
    id: str = Field(..., description="프로바이더 UUID.")
    slug: str = Field(..., description="고유 슬러그.")
    providerType: Literal["saml", "oidc"] = Field(..., description="프로바이더 타입(SAML/OIDC).")
    displayName: str = Field(..., description="표시 이름.")
    orgId: Optional[str] = Field(default=None, description="연결된 조직 UUID.")
    issuer: Optional[str] = Field(default=None, description="IdP Issuer/Entity ID.")
    audience: Optional[str] = Field(default=None, description="Audience 또는 Client ID.")
    spEntityId: Optional[str] = Field(default=None, description="SP Entity ID (SAML).")
    acsUrl: Optional[str] = Field(default=None, description="ACS URL (SAML).")
    metadataUrl: Optional[str] = Field(default=None, description="메타데이터 URL.")
    idpSsoUrl: Optional[str] = Field(default=None, description="IdP SSO URL.")
    authorizationUrl: Optional[str] = Field(default=None, description="OIDC Authorize URL.")
    tokenUrl: Optional[str] = Field(default=None, description="OIDC Token URL.")
    userinfoUrl: Optional[str] = Field(default=None, description="OIDC Userinfo URL.")
    redirectUri: Optional[str] = Field(default=None, description="Redirect URI.")
    scopes: List[str] = Field(default_factory=list, description="OIDC scopes.")
    attributeMapping: Dict[str, Any] = Field(default_factory=dict, description="클레임 매핑.")
    defaultPlanTier: Optional[str] = Field(default=None, description="기본 플랜 티어.")
    defaultRole: Optional[str] = Field(default=None, description="기본 RBAC 역할.")
    defaultOrgSlug: Optional[str] = Field(default=None, description="자동 생성 시 사용할 org slug.")
    autoProvisionOrgs: bool = Field(default=False, description="자동 워크스페이스 생성 여부.")
    enabled: bool = Field(default=True, description="활성화 여부.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터.")
    createdAt: Optional[str] = Field(default=None, description="생성 시각.")
    updatedAt: Optional[str] = Field(default=None, description="수정 시각.")
    credentials: Dict[str, Optional[str]] = Field(default_factory=dict, description="마스킹된 자격증명.")


class AdminSsoProviderListResponse(AdminBaseModel):
    items: List[AdminSsoProviderSchema] = Field(default_factory=list, description="SSO 프로바이더 목록.")


class AdminSsoProviderResponse(AdminBaseModel):
    provider: AdminSsoProviderSchema = Field(..., description="단일 프로바이더 정보.")


class AdminSsoProviderCreateRequest(AdminBaseModel):
    slug: str = Field(..., description="프로바이더 고유 슬러그.")
    providerType: Literal["saml", "oidc"] = Field(..., description="타입.")
    displayName: str = Field(..., description="표시 이름.")
    orgId: Optional[str] = Field(default=None, description="연결할 조직 ID.")
    issuer: Optional[str] = Field(default=None, description="IdP Issuer.")
    audience: Optional[str] = Field(default=None, description="Audience/Client ID.")
    spEntityId: Optional[str] = Field(default=None, description="SP Entity ID.")
    acsUrl: Optional[str] = Field(default=None, description="ACS URL.")
    metadataUrl: Optional[str] = Field(default=None, description="메타데이터 URL.")
    idpSsoUrl: Optional[str] = Field(default=None, description="IdP SSO URL.")
    authorizationUrl: Optional[str] = Field(default=None, description="OIDC Authorize URL.")
    tokenUrl: Optional[str] = Field(default=None, description="OIDC Token URL.")
    userinfoUrl: Optional[str] = Field(default=None, description="OIDC Userinfo URL.")
    redirectUri: Optional[str] = Field(default=None, description="Redirect URI.")
    scopes: List[str] = Field(default_factory=list, description="OIDC scopes.")
    attributeMapping: Dict[str, Any] = Field(default_factory=dict, description="클레임 매핑.")
    defaultPlanTier: Optional[str] = Field(default=None, description="기본 플랜 티어.")
    defaultRole: Optional[str] = Field(default="viewer", description="기본 RBAC 역할.")
    defaultOrgSlug: Optional[str] = Field(default=None, description="기본 org slug.")
    autoProvisionOrgs: bool = Field(default=False, description="워크스페이스 자동 생성.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터.")


class AdminSsoProviderUpdateRequest(AdminBaseModel):
    displayName: Optional[str] = Field(default=None, description="표시 이름.")
    issuer: Optional[str] = Field(default=None, description="IdP Issuer.")
    audience: Optional[str] = Field(default=None, description="Audience/Client ID.")
    spEntityId: Optional[str] = Field(default=None, description="SP Entity ID.")
    acsUrl: Optional[str] = Field(default=None, description="ACS URL.")
    metadataUrl: Optional[str] = Field(default=None, description="메타데이터 URL.")
    idpSsoUrl: Optional[str] = Field(default=None, description="IdP SSO URL.")
    authorizationUrl: Optional[str] = Field(default=None, description="OIDC Authorize URL.")
    tokenUrl: Optional[str] = Field(default=None, description="OIDC Token URL.")
    userinfoUrl: Optional[str] = Field(default=None, description="OIDC Userinfo URL.")
    redirectUri: Optional[str] = Field(default=None, description="Redirect URI.")
    scopes: Optional[List[str]] = Field(default=None, description="OIDC scopes.")
    attributeMapping: Optional[Dict[str, Any]] = Field(default=None, description="클레임 매핑.")
    defaultPlanTier: Optional[str] = Field(default=None, description="기본 플랜 티어.")
    defaultRole: Optional[str] = Field(default=None, description="기본 RBAC 역할.")
    defaultOrgSlug: Optional[str] = Field(default=None, description="기본 org slug.")
    autoProvisionOrgs: Optional[bool] = Field(default=None, description="워크스페이스 자동 생성.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="추가 메타데이터.")
    enabled: Optional[bool] = Field(default=None, description="활성화 여부.")


class AdminSsoCredentialUpsertRequest(AdminBaseModel):
    credentialType: str = Field(..., description="credential 종류(saml_idp_certificate 등).")
    secretValue: str = Field(..., description="새로운 secret 값.")


class AdminSsoCredentialResponse(AdminBaseModel):
    credentialType: str = Field(..., description="credential 종류.")
    maskedSecret: Optional[str] = Field(default=None, description="마스킹된 secret.")
    version: int = Field(..., description="버전.")


class AdminScimTokenSchema(AdminBaseModel):
    id: str = Field(..., description="토큰 UUID.")
    tokenPrefix: str = Field(..., description="첫 몇 글자 프리픽스.")
    description: Optional[str] = Field(default=None, description="설명.")
    createdBy: Optional[str] = Field(default=None, description="생성자.")
    createdAt: str = Field(..., description="생성 시각.")
    lastUsedAt: Optional[str] = Field(default=None, description="마지막 사용 시각.")
    expiresAt: Optional[str] = Field(default=None, description="만료 시각.")
    revokedAt: Optional[str] = Field(default=None, description="회수 시각.")


class AdminScimTokenListResponse(AdminBaseModel):
    items: List[AdminScimTokenSchema] = Field(default_factory=list, description="SCIM 토큰 목록.")


class AdminScimTokenCreateRequest(AdminBaseModel):
    description: Optional[str] = Field(default=None, description="설명.")
    expiresAt: Optional[str] = Field(default=None, description="만료 시각(ISO8601).")


class AdminScimTokenCreateResponse(AdminBaseModel):
    token: str = Field(..., description="새로운 SCIM Bearer 토큰(이번 응답에서만 노출).")


__all__ = [
    "AdminGuardrailEvaluateRequest",
    "AdminGuardrailEvaluateResponse",
    "AdminGuardrailPolicyResponse",
    "AdminGuardrailPolicySchema",
    "AdminGuardrailPolicyUpdateRequest",
    "AdminUiUxBannerSchema",
    "AdminUiUxCopySchema",
    "AdminUiUxDefaultsSchema",
    "AdminUiUxSettingsResponse",
    "AdminUiUxSettingsSchema",
    "AdminUiUxSettingsUpdateRequest",
    "AdminUiUxThemeSchema",
    "AdminLlmProfileListResponse",
    "AdminLlmProfileResponse",
    "AdminLlmProfileSchema",
    "AdminLlmProfileUpsertRequest",
    "AdminOpsApiKeyCollection",
    "AdminOpsApiKeyResponse",
    "AdminOpsApiKeyRotationSchema",
    "AdminOpsApiKeySchema",
    "AdminOpsApiKeyUpdateRequest",
    "AdminOpsAlertChannelCreateRequest",
    "AdminOpsAlertChannelPreviewRequest",
    "AdminOpsAlertChannelPreviewResponse",
    "AdminOpsAlertChannelResponse",
    "AdminOpsAlertChannelSchema",
    "AdminOpsAlertChannelStatusUpdateRequest",
    "AdminOpsAlertChannelUpdateRequest",
    "AdminAuditLogEntrySchema",
    "AdminAuditLogListResponse",
    "AdminOpsNewsPipelineResponse",
    "AdminOpsNewsPipelineSchema",
    "AdminOpsNewsPipelineUpdateRequest",
    "AdminOpsRunHistoryResponse",
    "AdminOpsRunRecordSchema",
    "AdminOpsScheduleListResponse",
    "AdminOpsScheduleSchema",
    "AdminOpsTriggerRequest",
    "AdminOpsTriggerResponse",
    "AdminAlertPresetUsageEntry",
    "AdminAlertPresetUsageResponse",
    "AdminAlertPresetBundleUsage",
    "AdminOpsQuickActionRequest",
    "AdminOpsQuickActionResponse",
    "AdminRagConfigResponse",
    "AdminRagConfigSchema",
    "AdminRagConfigUpdateRequest",
    "AdminRagFilterSchema",
    "AdminRagReindexRequest",
    "AdminRagReindexResponse",
    "AdminRagReindexHistoryResponse",
    "AdminRagEvidenceDiffSchema",
    "AdminRagPdfRectSchema",
    "AdminRagEvidenceAnchorSchema",
    "AdminRagEvidenceSelfCheckSchema",
    "AdminRagEvidenceDiffItemSchema",
    "AdminRagReindexRecordSchema",
    "AdminRagReindexQueueEntrySchema",
    "AdminRagReindexQueueResponse",
    "AdminRagSlaResponse",
    "AdminRagSlaSummary",
    "AdminRagSlaTimeseriesPoint",
    "AdminRagSlaViolation",
    "AdminRagReindexRetryRequest",
    "AdminRagReindexRetryResponse",
    "AdminRagSourceSchema",
    "AdminSessionCreateRequest",
    "AdminSessionResponse",
    "AdminSessionRevokeResponse",
    "AdminCredentialLoginRequest",
    "AdminSsoProviderSchema",
    "AdminSsoProviderListResponse",
    "AdminSsoProviderResponse",
    "AdminSsoProviderCreateRequest",
    "AdminSsoProviderUpdateRequest",
    "AdminSsoCredentialUpsertRequest",
    "AdminSsoCredentialResponse",
    "AdminScimTokenSchema",
    "AdminScimTokenListResponse",
    "AdminScimTokenCreateRequest",
    "AdminScimTokenCreateResponse",
    "AdminSystemPromptListResponse",
    "AdminSystemPromptSchema",
    "AdminSystemPromptUpdateRequest",
    "PlanQuickAdjustQuota",
    "PlanQuickAdjustRequest",
    "PromptChannel",
    "TossWebhookReplayRequest",
    "TossWebhookReplayResponse",
    "WebhookAuditEntrySchema",
    "WebhookAuditListResponse",
]
