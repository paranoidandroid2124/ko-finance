"""Build structured payloads for LaTeX-based event briefs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.logging import get_logger
from services import admin_ui_service
from services.rag_shared import safe_int

logger = get_logger(__name__)

_FALLBACK_PRIMARY = "#1F6FEB"
_FALLBACK_ACCENT = "#22C55E"


class BrandTheme(BaseModel):
    primary_color: str = Field(default=_FALLBACK_PRIMARY, alias="primaryColor")
    accent_color: str = Field(default=_FALLBACK_ACCENT, alias="accentColor")
    tagline: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ReportMeta(BaseModel):
    title: str = "이벤트 브리프"
    subtitle: Optional[str] = None
    task_id: str = Field(..., alias="taskId")
    actor: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="generatedAt")
    scope: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    brand: BrandTheme

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class CompanyMetric(BaseModel):
    label: str
    value: Optional[str] = None
    note: Optional[str] = None
    code: Optional[str] = None


class CompanyLink(BaseModel):
    label: str
    url: Optional[str] = None


class CompanyProfile(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    sector: Optional[str] = None
    event_headline: Optional[str] = None
    event_date: Optional[str] = None
    receipt_no: Optional[str] = None
    key_metrics: List[CompanyMetric] = Field(default_factory=list)
    links: List[CompanyLink] = Field(default_factory=list)


class SummaryBlock(BaseModel):
    overview: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


class RagMetrics(BaseModel):
    status: str = "completed"
    mode: Optional[str] = None
    queue_wait_ms: Optional[int] = Field(default=None, alias="queue_wait_ms")
    duration_ms: Optional[int] = Field(default=None, alias="duration_ms")
    total_elapsed_ms: Optional[int] = Field(default=None, alias="total_elapsed_ms")
    sla_target_ms: Optional[int] = Field(default=None, alias="sla_target_ms")

    model_config = ConfigDict(populate_by_name=True)


class EvidenceChange(BaseModel):
    field: str
    before: Optional[str] = None
    after: Optional[str] = None


class EvidenceSample(BaseModel):
    diff_type: str = Field(alias="diffType")
    source: Optional[str] = None
    section: Optional[str] = None
    quote: Optional[str] = None
    chunk_id: Optional[str] = Field(default=None, alias="chunkId")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    changes: List[EvidenceChange] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class EvidenceDiffSummary(BaseModel):
    total_changes: int = Field(default=0, alias="totalChanges")
    created: int = 0
    updated: int = 0
    removed: int = 0
    samples: List[EvidenceSample] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class SelfCheckMeta(BaseModel):
    verdict: Optional[str] = None
    score: Optional[float] = None
    explanation: Optional[str] = None


class EventEvidence(BaseModel):
    title: Optional[str] = None
    quote: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    urn: Optional[str] = None
    reliability: Optional[str] = None
    diff_type: Optional[str] = Field(default=None, alias="diff_type")
    source_url: Optional[str] = Field(default=None, alias="source_url")
    self_check: Optional[SelfCheckMeta] = Field(default=None, alias="self_check")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TraceMetrics(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    usd_cost: Optional[float] = None


class TraceEvent(BaseModel):
    name: str
    timestamp: Optional[str] = None


class TraceMeta(BaseModel):
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    span_id: Optional[str] = None
    metrics: Optional[TraceMetrics] = None
    events: List[TraceEvent] = Field(default_factory=list)


class AuditMeta(BaseModel):
    log_key: Optional[str] = None
    recorded_at: Optional[str] = None
    actor: Optional[str] = None
    message: Optional[str] = None


class EventBriefDocument(BaseModel):
    report: ReportMeta
    company: Optional[CompanyProfile] = None
    summary: Optional[SummaryBlock] = None
    rag: Optional[RagMetrics] = None
    diff_summary: Optional[EvidenceDiffSummary] = Field(default=None, alias="diff_summary")
    evidence: List[EventEvidence] = Field(default_factory=list)
    trace: Optional[TraceMeta] = None
    audit: Optional[AuditMeta] = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime: lambda value: value.isoformat()},
    )


def load_brand_theme() -> BrandTheme:
    """Load brand colours and tagline from admin UI settings."""

    try:
        settings = admin_ui_service.load_ui_settings()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.debug("UI settings unavailable: %s", exc, exc_info=True)
        return BrandTheme()

    if not isinstance(settings, Mapping):
        return BrandTheme()

    theme = settings.get("theme") if isinstance(settings.get("theme"), Mapping) else {}
    copy_block = settings.get("copy") if isinstance(settings.get("copy"), Mapping) else {}

    primary = str(theme.get("primaryColor") or _FALLBACK_PRIMARY)
    accent = str(theme.get("accentColor") or _FALLBACK_ACCENT)
    tagline = copy_block.get("welcomeSubcopy") if isinstance(copy_block.get("welcomeSubcopy"), str) else None

    return BrandTheme(primaryColor=primary, accentColor=accent, tagline=tagline)


def extract_scope_list(task: Mapping[str, Any]) -> List[str]:
    """Normalise scope detail information into a unique list."""

    scopes: List[str] = []
    detail = task.get("scopeDetail")
    if isinstance(detail, (list, tuple)):
        for item in detail:
            text = str(item).strip()
            if text and text not in scopes:
                scopes.append(text)

    if not scopes:
        scope_value = task.get("scope")
        if isinstance(scope_value, str):
            parts = [segment.strip() for segment in scope_value.split(",")]
            scopes = [part for part in parts if part]

    return scopes


def build_summary_block(task: Mapping[str, Any], diff: Optional[Mapping[str, Any]]) -> SummaryBlock:
    """Generate a default summary section based on task outcome."""

    status = str(task.get("status") or "completed")
    scopes = extract_scope_list(task)
    scope_text = ", ".join(scopes) if scopes else str(task.get("scope") or "전체")

    overview = f"{scope_text} 재색인 작업이 {status} 상태로 기록되었습니다."
    highlights: List[str] = []
    risks: List[str] = []
    actions: List[str] = []

    duration = safe_int(task.get("durationMs"))
    queue_wait = safe_int(task.get("queueWaitMs"))
    total_elapsed = safe_int(task.get("totalElapsedMs"))

    if duration is not None:
        highlights.append(f"처리 시간 {duration}ms")
    if queue_wait is not None and queue_wait > 0:
        highlights.append(f"큐 대기 {queue_wait}ms")
    if total_elapsed is not None and total_elapsed != duration:
        highlights.append(f"총 소요 {total_elapsed}ms")

    if diff and isinstance(diff, Mapping):
        created = safe_int(diff.get("created")) or 0
        updated = safe_int(diff.get("updated")) or 0
        removed = safe_int(diff.get("removed")) or 0
        total = safe_int(diff.get("totalChanges")) or (created + updated + removed)

        if total:
            highlights.append(f"Evidence 변경 {total}건 (신규 {created}, 갱신 {updated}, 제거 {removed})")
        if removed:
            risks.append("삭제된 근거가 있어 검토가 필요합니다.")

    if status.lower() != "completed":
        risks.append("작업이 완료되지 않았습니다. Langfuse trace를 확인하세요.")
        actions.append("RAG 설정과 Langfuse trace를 확인해 후속 조치를 수행하세요.")

    return SummaryBlock(
        overview=overview,
        highlights=highlights,
        risks=risks,
        actions=actions,
    )


def build_diff_summary(diff: Optional[Mapping[str, Any]]) -> Optional[EvidenceDiffSummary]:
    """Normalise evidence diff payloads into the document model."""

    if not diff or not isinstance(diff, Mapping):
        return None

    samples_raw = diff.get("samples")
    samples: List[EvidenceSample] = []
    if isinstance(samples_raw, Iterable):
        for sample in samples_raw:
            if not isinstance(sample, Mapping):
                continue
            try:
                changes_raw = sample.get("changes")
                changes: List[EvidenceChange] = []
                if isinstance(changes_raw, Iterable):
                    for change in changes_raw:
                        if isinstance(change, Mapping) and change.get("field"):
                            changes.append(
                                EvidenceChange(
                                    field=str(change.get("field")),
                                    before=str(change.get("before")) if change.get("before") is not None else None,
                                    after=str(change.get("after")) if change.get("after") is not None else None,
                                )
                            )
                payload = dict(sample)
                payload["changes"] = changes
                samples.append(EvidenceSample.model_validate(payload))
            except ValidationError as exc:
                logger.debug("Skipped diff sample due to validation error: %s", exc)
                continue

    summary_payload = {
        "totalChanges": safe_int(diff.get("totalChanges")),
        "created": safe_int(diff.get("created")),
        "updated": safe_int(diff.get("updated")),
        "removed": safe_int(diff.get("removed")),
        "samples": samples,
    }

    try:
        return EvidenceDiffSummary.model_validate(summary_payload)
    except ValidationError as exc:  # pragma: no cover - defensive guard
        logger.debug("Failed to build diff summary: %s", exc)
        return None


def build_evidence_items(
    evidence: Optional[Iterable[Mapping[str, Any]]],
    diff_summary: Optional[EvidenceDiffSummary],
) -> List[EventEvidence]:
    """Create evidence cards for the brief."""

    items: List[EventEvidence] = []
    source_iterable: Iterable[Mapping[str, Any]]

    if evidence:
        source_iterable = (item for item in evidence if isinstance(item, Mapping))
    elif diff_summary:
        source_iterable = (
            {
                "title": sample.section or sample.source or "Evidence",
                "quote": sample.quote,
                "section": sample.section,
                "urn": sample.chunk_id,
                "diff_type": sample.diff_type,
            }
            for sample in diff_summary.samples
        )
    else:
        source_iterable = []

    for entry in source_iterable:
        try:
            items.append(EventEvidence.model_validate(entry))
        except ValidationError as exc:  # pragma: no cover
            logger.debug("Skipping evidence entry: %s", exc)
            continue

    return items


def build_rag_metrics(task: Mapping[str, Any], *, sla_target_ms: Optional[int]) -> RagMetrics:
    """Extract numeric RAG metrics from the task record."""

    payload = {
        "status": str(task.get("status") or "completed"),
        "mode": task.get("ragMode"),
        "queue_wait_ms": safe_int(task.get("queueWaitMs")),
        "duration_ms": safe_int(task.get("durationMs")),
        "total_elapsed_ms": safe_int(task.get("totalElapsedMs")),
        "sla_target_ms": safe_int(task.get("slaTargetMs")) or sla_target_ms,
    }
    return RagMetrics.model_validate(payload)


def make_event_brief(
    *,
    task: Mapping[str, Any],
    diff: Optional[Mapping[str, Any]] = None,
    evidence: Optional[Iterable[Mapping[str, Any]]] = None,
    trace: Optional[Mapping[str, Any]] = None,
    audit: Optional[Mapping[str, Any]] = None,
    company: Optional[Mapping[str, Any]] = None,
    summary: Optional[Mapping[str, Any]] = None,
    sla_target_ms: Optional[int] = None,
) -> EventBriefDocument:
    """Assemble the complete event brief document model."""

    brand = load_brand_theme()
    scopes = extract_scope_list(task)

    report = ReportMeta(
        taskId=str(task.get("taskId") or task.get("task_id") or "unknown-task"),
        actor=str(task.get("actor") or ""),
        scope=scopes,
        note=str(task.get("note")) if task.get("note") else None,
        subtitle=str(task.get("scope") or ", ".join(scopes) or "재색인 결과"),
        brand=brand,
    )

    diff_summary = build_diff_summary(diff)
    evidence_items = build_evidence_items(evidence, diff_summary)

    if summary and isinstance(summary, Mapping):
        summary_block = SummaryBlock.model_validate(summary)
    else:
        summary_block = build_summary_block(task, diff)

    rag_metrics = build_rag_metrics(task, sla_target_ms=sla_target_ms)

    company_block: Optional[CompanyProfile] = None
    if company and isinstance(company, Mapping):
        try:
            company_block = CompanyProfile.model_validate(company)
        except ValidationError as exc:
            logger.debug("Company profile skipped: %s", exc)

    trace_block: Optional[TraceMeta] = None
    if trace and isinstance(trace, Mapping):
        trace_payload = dict(trace)
        events = []
        for event in trace_payload.get("events", []):
            if isinstance(event, Mapping):
                try:
                    events.append(TraceEvent.model_validate(event))
                except ValidationError:
                    continue
        trace_payload["events"] = events
        metrics_payload = trace_payload.get("metrics")
        if isinstance(metrics_payload, Mapping):
            try:
                trace_payload["metrics"] = TraceMetrics.model_validate(metrics_payload)
            except ValidationError:
                trace_payload["metrics"] = None
        try:
            trace_block = TraceMeta.model_validate(trace_payload)
        except ValidationError as exc:
            logger.debug("Trace payload skipped: %s", exc)

    audit_block: Optional[AuditMeta] = None
    if audit and isinstance(audit, Mapping):
        try:
            audit_block = AuditMeta.model_validate(audit)
        except ValidationError as exc:
            logger.debug("Audit payload skipped: %s", exc)

    return EventBriefDocument(
        report=report,
        company=company_block,
        summary=summary_block,
        rag=rag_metrics,
        diff_summary=diff_summary,
        evidence=evidence_items,
        trace=trace_block,
        audit=audit_block,
    )


def event_brief_to_dict(document: EventBriefDocument) -> Dict[str, Any]:
    """Serialise the event brief into a JSON-friendly dictionary."""

    return document.model_dump(mode="json", by_alias=True, exclude_none=True)


__all__ = [
    "AuditMeta",
    "BrandTheme",
    "CompanyProfile",
    "EventBriefDocument",
    "EventEvidence",
    "EvidenceDiffSummary",
    "RagMetrics",
    "SummaryBlock",
    "TraceMeta",
    "event_brief_to_dict",
    "load_brand_theme",
    "make_event_brief",
]

