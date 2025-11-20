"""Celery tasks orchestrating filings and Market Mood pipelines."""

from __future__ import annotations

import logging
import os
import uuid
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union, cast

from celery import shared_task
from pydantic import ValidationError
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import llm.llm_service as llm_service
from core.env import env_bool, env_float, env_int, env_str
from database import SessionLocal
from ingest.dart_seed import seed_recent_filings as seed_recent_filings_job
from ingest.news_fetcher import fetch_news_batch
from models.chat import ChatMessage, ChatSession
from models.fact import ExtractedFact
from models.filing import (
    Filing,
    STATUS_PENDING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PARTIAL,
    ANALYSIS_ANALYZED,
    ANALYSIS_FAILED,
    ANALYSIS_PARTIAL,
)
from models.news import NewsObservation, NewsSignal, NewsWindowAggregate
from models.ingest_dead_letter import IngestDeadLetter
from services.memory.offline_pipeline import run_long_term_update
from services.memory.health import lightmem_health_summary
from models.summary import Summary
from parse.pdf_parser import extract_chunks
from parse.xml_parser import extract_chunks_from_xml
from schemas.news import NewsArticleCreate
from services import (
    admin_ops_service,
    alert_service,
    chat_service,
    storage_service,
    vector_service,
    ocr_service,
    plan_service,
    lightmem_rate_limiter,
    event_study_service,
    market_data_service,
    security_metadata_service,
    ingest_dlq_service,
    table_extraction_service,
    rag_grid,
    watchlist_service,
)
from services.evidence_service import save_evidence_snapshot
from services.ingest_errors import FatalIngestError, TransientIngestError
from services.aggregation.sector_classifier import assign_article_to_sector
from services.aggregation.sector_metrics import compute_sector_daily_metrics, compute_sector_window_metrics
from services.aggregation.news_metrics import compute_news_window_metrics
from services.notification_service import dispatch_notification, send_telegram_alert
from services.reliability.source_reliability import score_article as score_source_reliability
from services.aggregation.news_statistics import summarize_news_signals, build_top_topics
from services.daily_brief_service import (
    DAILY_BRIEF_CHANNEL,
    DAILY_BRIEF_OUTPUT_ROOT,
    DigestQuotaExceeded,
    build_daily_brief_payload,
    cleanup_daily_brief_artifacts,
    has_brief_been_generated,
    record_brief_generation,
    render_daily_brief_document,
)
from services.maintenance.data_retention import apply_retention_policies
from services.compliance import dsar_service


def _parse_recipients(value: Optional[str]) -> List[str]:
    if not value:
        return []
    recipients: List[str] = []
    for entry in value.split(","):
        trimmed = entry.strip()
        if trimmed:
            recipients.append(trimmed)
    return recipients


def _set_filing_fields(filing: Filing, **updates: Any) -> None:
    typed = cast(Any, filing)
    for field, value in updates.items():
        setattr(typed, field, value)


ALERT_FAILURE_SLACK_TARGETS = _parse_recipients(env_str("ALERTS_FAILURE_SLACK_TARGETS"))
ALERT_FAILURE_EMAIL_TARGETS = _parse_recipients(env_str("ALERTS_FAILURE_EMAIL_TARGETS"))
ALERT_FAILURE_EMAIL_SUBJECT = (
    env_str("ALERTS_FAILURE_EMAIL_SUBJECT") or "[Nuvien] Alert 채널 오류 감지"
)
from services.news_text import sanitize_news_summary
from services.news_ticker_resolver import resolve_news_ticker
from services.audit_log import audit_ingest_event
from services.ingest_metrics import (
    observe_latency as ingest_observe_latency,
    record_error as ingest_record_error,
    record_result as ingest_record_result,
    record_retry as ingest_record_retry,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_OCR_MIN_TEXT_LENGTH = env_int("OCR_TRIGGER_MIN_TEXT_LENGTH", 400, minimum=0)
_OCR_ENABLE_LOG = env_bool("OCR_LOG_DECISIONS", True)
_OCR_PAGE_LIMIT = env_int("OCR_TRIGGER_MAX_PAGES", 15, minimum=1)
TELEGRAM_NOTIFY_POS_NEG_ONLY = env_bool("TELEGRAM_NOTIFY_POS_NEG_ONLY", True)
INGEST_TASK_MAX_RETRIES = env_int("INGEST_TASK_MAX_RETRIES", 4, minimum=0)
INGEST_RETRY_BASE_SECONDS = env_int("INGEST_TASK_RETRY_BASE_SECONDS", 30, minimum=5)
INGEST_RETRY_MAX_SECONDS = env_int("INGEST_TASK_RETRY_MAX_SECONDS", 600, minimum=30)
PROCESS_STAGE = "process.filing"


@dataclass
class StageResult:
    name: str
    critical: bool
    success: bool
    error: Optional[str] = None
    skipped: bool = False


class StageSkip(Exception):
    """Signal that a stage should be skipped without failing the pipeline."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Sentiment aliases for summaries
_SENTIMENT_ALIASES: Dict[str, str] = {
    "positive": "positive",
    "\uae09\uc815": "positive",  # 긍정
    "negative": "negative",
    "\ubd80\uc815": "negative",  # 부정
    "neutral": "neutral",
    "\uc911\ub9bd": "neutral",  # 중립
}

def _normalize_sentiment(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip().lower()
        return _SENTIMENT_ALIASES.get(candidate)
    return None


def _safe_uuid(value: Any) -> Optional[uuid.UUID]:
    try:
        if value:
            return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
    return None


def _count_text_characters(chunks: Iterable[Dict[str, Any]], *, source: Optional[str] = None) -> int:
    total = 0
    for chunk in chunks:
        if chunk.get("type") != "text":
            continue
        if source and chunk.get("source") != source:
            continue
        content = chunk.get("content")
        if isinstance(content, str):
            total += len(content)
    return total


def _map_sentiment_label(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score <= -0.2:
        return "negative"
    if score >= 0.2:
        return "positive"
    return "neutral"


def _store_news_vector_entry(
    news_signal: NewsSignal,
    *,
    chunk_text: Optional[str],
    topics: Sequence[str],
    sentiment_score: Optional[float],
    reliability: Optional[float],
) -> None:
    text = (chunk_text or "").strip()
    if not text:
        return
    if not getattr(news_signal, "id", None):
        logger.debug("Skipping news vector upsert because signal ID is missing.")
        return

    published_at = getattr(news_signal, "published_at", None)
    published_iso: Optional[str] = None
    published_ts: Optional[float] = None
    if isinstance(published_at, datetime):
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        published_iso = published_at.isoformat()
        published_ts = published_at.timestamp()

    cleaned_topics: List[str] = []
    seen_topics: set[str] = set()
    for topic in topics or []:
        if not isinstance(topic, str):
            continue
        normalized = topic.strip()
        if not normalized or normalized in seen_topics:
            continue
        cleaned_topics.append(normalized)
        seen_topics.add(normalized)

    sentiment_label = _map_sentiment_label(sentiment_score)
    metadata: Dict[str, Any] = {
        "source_type": "news",
        "source_id": str(news_signal.id),
        "title": news_signal.headline,
        "publisher": news_signal.source,
        "source": news_signal.source,
        "ticker": news_signal.ticker,
        "article_url": news_signal.url,
        "license_type": getattr(news_signal, "license_type", None),
        "license_url": getattr(news_signal, "license_url", None),
        "source_reliability": reliability,
        "summary": text,
    }
    if published_iso:
        metadata["filed_at"] = published_iso
        metadata["filed_at_ts"] = published_ts
        metadata["published_at"] = published_iso
    if sentiment_label:
        metadata["sentiment"] = sentiment_label
        metadata["sentiments"] = [sentiment_label]
    if sentiment_score is not None:
        metadata["sentiment_score"] = float(sentiment_score)
    if cleaned_topics:
        metadata["topics"] = cleaned_topics
    if news_signal.url:
        metadata["viewer_url"] = news_signal.url

    chunk_id = f"news:{news_signal.id}"
    chunk_payload = {
        "id": f"{chunk_id}#0",
        "content": text,
        "metadata": metadata,
    }
    try:
        vector_service.store_chunk_vectors(
            chunk_id,
            [chunk_payload],
            metadata=metadata,
        )
        logger.debug("Stored news vector chunk for %s", news_signal.url)
    except Exception as exc:
        logger.warning("Failed to store news vector for %s: %s", news_signal.url, exc, exc_info=True)


UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

DIGEST_ZONE = ZoneInfo("Asia/Seoul")
SECTOR_ZONE = ZoneInfo("Asia/Seoul")
DIGEST_TOP_LIMIT = env_int("DAILY_DIGEST_TOP_N", 3, minimum=1)
DIGEST_BASE_URL = env_str("FILINGS_DASHBOARD_URL", "https://kofilot.com/filings")
DIGEST_CHANNEL = "telegram"
SUMMARY_RECENT_TURNS = env_int("CHAT_MEMORY_RECENT_TURNS", 3, minimum=1)
SUMMARY_TRIGGER_MESSAGES = env_int("CHAT_SUMMARY_TRIGGER_MESSAGES", 20, minimum=6)


def _ingest_retry_delay(attempt: int) -> int:
    clamped = max(0, attempt)
    delay = INGEST_RETRY_BASE_SECONDS * (2 ** clamped)
    return min(delay, INGEST_RETRY_MAX_SECONDS)


def _retry_or_dead_letter(
    task,
    *,
    db: Session,
    filing_id: str,
    filing: Optional[Filing],
    exc: Exception,
) -> None:
    receipt_no = getattr(filing, "receipt_no", None)
    corp_code = getattr(filing, "corp_code", None)
    ticker = getattr(filing, "ticker", None)

    def _notify(letter) -> None:
        try:
            audit_ingest_event(
                action="ingest.dlq",
                target_id=receipt_no or filing_id,
                extra={
                    "task": getattr(task, "name", "m1.process_filing"),
                    "retries": getattr(task.request, "retries", 0),
                    "corp_code": corp_code,
                    "ticker": ticker,
                    "dlq_id": str(letter.id),
                },
            )
        except Exception as log_exc:  # pragma: no cover - audit best-effort
            logger.warning("Failed to record ingest audit for filing %s: %s", filing_id, log_exc, exc_info=True)

    _handle_ingest_exception(
        task,
        exc,
        payload={"filing_id": filing_id},
        receipt_no=receipt_no or filing_id,
        corp_code=corp_code,
        ticker=ticker,
        db=db,
        on_dead_letter=_notify,
    )


def _handle_ingest_exception(
    task,
    exc: Exception,
    *,
    payload: Mapping[str, Any],
    receipt_no: Optional[str] = None,
    corp_code: Optional[str] = None,
    ticker: Optional[str] = None,
    db: Optional[Session] = None,
    on_dead_letter: Optional[Callable[[IngestDeadLetter], None]] = None,
) -> None:
    """Retry or persist the failure for ingest tasks."""
    if isinstance(exc, TransientIngestError):
        retries = getattr(task.request, "retries", 0)
        if retries >= INGEST_TASK_MAX_RETRIES:
            exc = FatalIngestError(f"{getattr(task, 'name', 'ingest-task')} exceeded retry budget: {exc}")
        else:
            countdown = _ingest_retry_delay(retries)
            ingest_record_retry(getattr(task, "name", "ingest-task"))
            raise task.retry(exc=exc, countdown=countdown)

    if isinstance(exc, FatalIngestError):
        session = db or SessionLocal()
        try:
            task_name = getattr(task, "name", "ingest-task")
            retries = getattr(task.request, "retries", 0)
            letter = ingest_dlq_service.record_dead_letter(
                session,
                task_name=task_name,
                payload=payload,
                error=str(exc),
                retries=retries,
                receipt_no=receipt_no,
                corp_code=corp_code,
                ticker=ticker,
            )
            if on_dead_letter:
                on_dead_letter(letter)
            try:
                audit_ingest_event(
                    action="ingest.dlq",
                    target_id=receipt_no or str(letter.id),
                    extra={
                        "task": task_name,
                        "dlq_id": str(letter.id),
                        "retries": retries,
                        "corp_code": corp_code,
                        "ticker": ticker,
                        "receipt_no": receipt_no,
                        "payload": letter.payload,
                    },
                )
            except Exception as audit_exc:  # pragma: no cover - audit best effort
                logger.debug("Failed to record ingest DLQ audit entry: %s", audit_exc, exc_info=True)
        finally:
            if db is None:
                session.close()
        raise exc

    raise exc

NEWS_FETCH_LIMIT = env_int("NEWS_FETCH_LIMIT", 5, minimum=1)
NEWS_SUMMARY_MAX_CHARS = env_int("NEWS_SUMMARY_MAX_CHARS", 480, minimum=120)
NEWS_RETENTION_DAYS = env_int("NEWS_RETENTION_DAYS", 45, minimum=7)
LIGHTMEM_HEALTH_ALERT_ENABLED = env_bool("LIGHTMEM_HEALTH_ALERT_ENABLED", True)
LIGHTMEM_HEALTH_ALERT_CHANNEL = env_str("LIGHTMEM_HEALTH_ALERT_CHANNEL", "slack")
_LIGHTMEM_HEALTH_ALERT_TARGETS = [
    target.strip()
    for target in (env_str("LIGHTMEM_HEALTH_ALERT_TARGETS", "") or "").split(",")
    if target.strip()
]

CATEGORY_TRANSLATIONS: Dict[str, str] = {
    "capital_increase": "증자",
    "증자": "증자",
    "share_issuance": "증자",
    "buyback": "자사주 매입/소각",
    "share_buyback": "자사주 매입/소각",
    "자사주 매입/소각": "자사주 매입/소각",
    "cb_bw": "전환사채·신주인수권부사채",
    "convertible": "전환사채·신주인수권부사채",
    "전환사채·신주인수권부사채": "전환사채·신주인수권부사채",
    "large_contract": "대규모 공급·수주 계약",
    "major_contract": "대규모 공급·수주 계약",
    "대규모 공급·수주 계약": "대규모 공급·수주 계약",
    "litigation": "소송/분쟁",
    "lawsuit": "소송/분쟁",
    "소송/분쟁": "소송/분쟁",
    "mna": "M&A/합병·분할",
    "m&a": "M&A/합병·분할",
    "merger": "M&A/합병·분할",
    "M&A/합병·분할": "M&A/합병·분할",
    "합병": "M&A/합병·분할",
    "governance": "지배구조·임원 변경",
    "governance_change": "지배구조·임원 변경",
    "지배구조·임원 변경": "지배구조·임원 변경",
    "audit_opinion": "감사 의견",
    "감사 의견": "감사 의견",
    "periodic_report": "정기·수시 보고서",
    "regular_report": "정기·수시 보고서",
    "정기·수시 보고서": "정기·수시 보고서",
    "securities_registration": "증권신고서/투자설명서",
    "registration": "증권신고서/투자설명서",
    "증권신고서/투자설명서": "증권신고서/투자설명서",
    "insider_ownership": "임원·주요주주 지분 변동",
    "insider_trading": "임원·주요주주 지분 변동",
    "임원·주요주주 지분 변동": "임원·주요주주 지분 변동",
    "correction": "정정 공시",
    "revision": "정정 공시",
    "정정 공시": "정정 공시",
    "ir_presentation": "IR/설명회",
    "ir": "IR/설명회",
    "ir/설명회": "IR/설명회",
    "dividend": "배당/주주환원",
    "shareholder_return": "배당/주주환원",
    "배당/주주환원": "배당/주주환원",
    "other": "기타",
    "기타": "기타",
}


def _normalize_category_label(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    trimmed = value.strip()
    lower = trimmed.lower()
    return CATEGORY_TRANSLATIONS.get(lower) or CATEGORY_TRANSLATIONS.get(trimmed) or trimmed


def _build_vector_metadata(filing: Filing) -> Dict[str, Any]:
    """Assemble metadata fields to persist alongside vector chunks."""
    ticker = cast(Optional[str], filing.ticker)
    corp_code = cast(Optional[str], filing.corp_code)
    corp_name = cast(Optional[str], filing.corp_name)
    market = cast(Optional[str], filing.market)
    report_name = cast(Optional[str], filing.report_name)
    category = cast(Optional[str], filing.category)
    meta: Dict[str, Any] = {
        "ticker": ticker,
        "corp_code": corp_code,
        "corp_name": corp_name,
        "market": market,
        "report_name": report_name,
        "category": category,
    }
    raw_urls = cast(Optional[Mapping[str, Any]], filing.urls)
    urls = raw_urls if isinstance(raw_urls, Mapping) else {}
    viewer_url = urls.get("viewer") if isinstance(urls, Mapping) else None
    download_url = (
        urls.get("download")
        if isinstance(urls, Mapping)
        else None
    )
    pdf_url = (
        urls.get("pdf")
        if isinstance(urls, Mapping)
        else None
    )
    if viewer_url:
        meta["viewer_url"] = viewer_url
        meta["document_url"] = viewer_url
    if download_url:
        meta["download_url"] = download_url
        meta.setdefault("document_url", download_url)
    elif pdf_url:
        meta.setdefault("document_url", pdf_url)
    receipt_no = cast(Optional[str], filing.receipt_no)
    if receipt_no:
        meta["receipt_no"] = receipt_no
    filed_at = cast(Optional[datetime], filing.filed_at)
    if filed_at:
        if filed_at.tzinfo is None:
            filed_at = filed_at.replace(tzinfo=timezone.utc)
        meta["filed_at_iso"] = filed_at.isoformat()
        meta["filed_at_ts"] = filed_at.timestamp()
    return {key: value for key, value in meta.items() if value not in (None, "")}


def _open_session() -> Session:
    return SessionLocal()


def _build_alert_failure_message(events: Sequence[Mapping[str, Any]]) -> str:
    lines = [":rotating_light: *알림 채널 오류 감지*"]
    max_rules = 5
    for idx, event in enumerate(events):
        if idx >= max_rules:
            break
        rule_name = event.get("ruleName") or event.get("ruleId")
        plan_tier = event.get("planTier")
        org_id = event.get("orgId")
        lines.append(
            f"- {rule_name} (플랜 {plan_tier}{' · Org ' + str(org_id) if org_id else ''})"
        )
        for channel in (event.get("channels") or [])[:3]:
            channel_name = channel.get("channel")
            error_text = channel.get("error") or "오류"
            retry_after = channel.get("retryAfter")
            retry_label = f" · 재시도 {retry_after}" if retry_after else ""
            lines.append(f"    • {channel_name}: {error_text}{retry_label}")
    remaining = len(events) - max_rules
    if remaining > 0:
        lines.append(f"... 추가 {remaining}건")
    return "\n".join(lines)


def _notify_alert_channel_failures(events: Sequence[Mapping[str, Any]]) -> None:
    if not events:
        return
    if not ALERT_FAILURE_SLACK_TARGETS and not ALERT_FAILURE_EMAIL_TARGETS:
        logger.debug("Channel failures detected but no alert recipients configured.")
        return
    message = _build_alert_failure_message(events)
    if ALERT_FAILURE_SLACK_TARGETS:
        try:
            dispatch_notification(
                "slack",
                message,
                targets=ALERT_FAILURE_SLACK_TARGETS,
                metadata={"markdown": message},
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to dispatch Slack channel failure alert: %s", exc, exc_info=True)
    if ALERT_FAILURE_EMAIL_TARGETS:
        try:
            dispatch_notification(
                "email",
                message,
                targets=ALERT_FAILURE_EMAIL_TARGETS,
                metadata={"subject": ALERT_FAILURE_EMAIL_SUBJECT},
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to dispatch email channel failure alert: %s", exc, exc_info=True)


@shared_task(
    name="alerts.evaluate_rules",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def evaluate_alert_rules(self, limit: int = 1000, prefetch_factor: Optional[int] = None) -> Dict[str, int]:
    """Periodic task that evaluates alert rules and dispatches notifications."""
    db = _open_session()
    task_id = getattr(self.request, "id", None)
    if limit < 1:
        logger.warning("Alert evaluation limit must be positive. Received %s. Falling back to 1.", limit)
        limit = 1
    try:
        result = alert_service.evaluate_due_alerts(
            db,
            limit=limit,
            prefetch_factor=prefetch_factor,
            task_id=task_id,
        )
        db.commit()
        logger.info(
            "Alert evaluation completed (task=%s): evaluated=%s triggered=%s skipped=%s errors=%s plans=%s channelFailures=%s",
            task_id,
            result.get("evaluated"),
            result.get("triggered"),
            result.get("skipped"),
            result.get("errors"),
            result.get("by_plan"),
            len(result.get("channelFailures") or []),
        )
        channel_failures = result.get("channelFailures") or []
        if channel_failures:
            _notify_alert_channel_failures(channel_failures)
        return result
    except Exception as exc:  # pragma: no cover - Celery runtime guard
        db.rollback()
        logger.error(
            "Alert evaluation failed (task=%s, retry=%s/%s): %s",
            task_id,
            getattr(self.request, "retries", 0),
            getattr(self, "max_retries", 0),
            exc,
            exc_info=True,
        )
        raise
    finally:
        db.close()


def _ensure_pdf_path(filing: Filing) -> Optional[str]:
    file_path = cast(Optional[str], filing.file_path)
    if file_path and Path(file_path).is_file():
        return file_path

    source_files = cast(Optional[Mapping[str, Any]], filing.source_files) or {}
    pdf_path = source_files.get("pdf") if isinstance(source_files, dict) else None
    if pdf_path and Path(pdf_path).is_file():
        _set_filing_fields(filing, file_path=pdf_path)
        return pdf_path

    urls = cast(Optional[Mapping[str, Any]], filing.urls) or {}
    object_name = (
        urls.get("storage_object")
        or urls.get("minio_object")
        or urls.get("object_name")
    )
    if object_name and storage_service.is_enabled():
        receipt_no = cast(Optional[str], filing.receipt_no)
        filing_id = cast(uuid.UUID, filing.id)
        local_path = Path(UPLOAD_DIR) / f"{receipt_no or filing_id}.pdf"
        downloaded = storage_service.download_file(object_name, str(local_path))
        if downloaded:
            _set_filing_fields(filing, file_path=downloaded)
            return downloaded

    logger.warning("PDF file not available for filing %s", filing.id)
    return None


def _load_xml_paths(filing: Filing) -> List[str]:
    source_files = cast(Optional[Mapping[str, Any]], filing.source_files) or {}
    xml_paths = source_files.get("xml") if isinstance(source_files, dict) else None
    if not xml_paths:
        return []

    cache_dir = Path(UPLOAD_DIR) / "xml_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    resolved_paths: List[str] = []

    for entry in xml_paths:
        candidate_path: Optional[str] = None
        object_name: Optional[str] = None
        remote_url: Optional[str] = None

        if isinstance(entry, str):
            candidate_path = entry
        elif isinstance(entry, dict):
            raw_path = entry.get("path")
            candidate_path = str(raw_path) if raw_path else None
            object_name = entry.get("object") or entry.get("minio_object") or entry.get("object_name")
            remote_url = entry.get("url")
        else:
            continue

        if candidate_path and Path(candidate_path).is_file():
            resolved_paths.append(candidate_path)
            continue

        if object_name and storage_service.is_enabled():
            target_path = cache_dir / Path(object_name).name
            downloaded = storage_service.download_file(object_name, str(target_path))
            if downloaded:
                resolved_paths.append(downloaded)
                continue

        if remote_url and isinstance(remote_url, str) and remote_url.startswith("http"):
            try:
                import httpx  # Imported lazily to avoid hard dependency at module load time
                from urllib.parse import urlparse

                response = httpx.get(remote_url, timeout=15.0)
                response.raise_for_status()
                parsed = urlparse(remote_url)
                filename = Path(parsed.path).name or f"{filing.id}.xml"
                target_path = cache_dir / filename
                target_path.write_text(response.text, encoding="utf-8")
                resolved_paths.append(str(target_path))
                continue
            except Exception as exc:
                logger.warning("Failed to fetch XML from %s for filing %s: %s", remote_url, filing.id, exc)

        logger.warning("XML file not available for filing %s (entry=%s)", filing.id, entry)

    if not resolved_paths:
        logger.warning("No XML files could be resolved for filing %s.", filing.id)

    return resolved_paths


def _save_chunks(
    filing: Filing,
    chunks: List[Dict[str, Any]],
    db: Session,
    *,
    commit: bool = True,
) -> None:
    combined_raw = "\n\n".join(
        chunk["content"] for chunk in chunks if isinstance(chunk.get("content"), str)
    )
    _set_filing_fields(filing, chunks=chunks, raw_md=combined_raw)
    if commit:
        db.commit()


def _normalize_facts(facts_payload: Any) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    if isinstance(facts_payload, list):
        for item in facts_payload:
            if isinstance(item, dict):
                facts.append(item)
    elif isinstance(facts_payload, dict):
        for key, value in facts_payload.items():
            if isinstance(value, dict):
                item = {"field": key, **value}
                facts.append(item)
    return facts


def _save_facts(filing: Filing, facts: List[Dict[str, Any]], db: Session) -> None:
    db.query(ExtractedFact).filter(ExtractedFact.filing_id == filing.id).delete()
    for fact in facts:
        anchor = fact.get("anchor") or {}
        new_fact = ExtractedFact(
            filing_id=filing.id,
            fact_type=fact.get("field") or fact.get("fact_type"),
            value=str(fact.get("value")) if fact.get("value") is not None else "",
            unit=fact.get("unit"),
            currency=fact.get("currency"),
            anchor_page=anchor.get("page"),
            anchor_quote=anchor.get("quote"),
            anchor=anchor,
            method=fact.get("method", "llm_extraction"),
            confidence_score=fact.get("confidence"),
        )
        db.add(new_fact)
    db.commit()


def _save_summary(filing: Filing, summary: Dict[str, Any], db: Session) -> None:
    record = db.query(Summary).filter(Summary.filing_id == filing.id).first()
    if not record:
        record = Summary(filing_id=filing.id)
        db.add(record)
    typed_record = cast(Any, record)
    typed_record.who = summary.get("who")
    typed_record.what = summary.get("what")
    typed_record.when = summary.get("when")
    typed_record.where = summary.get("where")
    typed_record.how = summary.get("how")
    typed_record.why = summary.get("why")
    typed_record.insight = summary.get("insight")
    typed_record.confidence_score = summary.get("confidence_score")
    sentiment_label = summary.get("sentiment") or summary.get("sentiment_label")
    sentiment_reason = summary.get("sentiment_reason")
    normalized_label = _normalize_sentiment(sentiment_label)
    normalized_reason: Optional[str] = None
    if isinstance(sentiment_reason, str):
        stripped = sentiment_reason.strip()
        if stripped:
            normalized_reason = stripped
    typed_record.sentiment_label = normalized_label
    typed_record.sentiment_reason = normalized_reason
    db.commit()


def _format_notification(filing: Filing, summary: Dict[str, Any]) -> str:
    parts = ["*[DART Watcher+]*"]
    report_name = cast(Optional[str], filing.report_name)
    fallback_title = cast(Optional[str], filing.title)
    title = report_name or fallback_title or "Untitled filing"
    ticker = cast(Optional[str], filing.ticker)
    if ticker:
        parts.append(f"*{ticker}* {title}")
    else:
        parts.append(title)
    insight = summary.get("insight") or summary.get("what") or "Summary is not available."
    parts.append(f"- Summary: {insight}")
    urls = cast(Optional[Mapping[str, Any]], filing.urls) or {}
    viewer_url = urls.get("viewer")
    if viewer_url:
        parts.append(f"[View original document]({viewer_url})")
    parts.append("_(For information only. This is not investment advice.)_")
    return "\n".join(parts)


@shared_task(name="system.health_check")
def health_check() -> str:
    return "ok"


def _format_lightmem_health_markdown(summary: Dict[str, Any]) -> str:
    lines = [f"*Status*: `{summary.get('status', 'unknown')}`"]
    checks = summary.get("checks") or {}
    for name, result in checks.items():
        status = result.get("status", "unknown")
        pieces: List[str] = []
        latency = result.get("latencyMs")
        if latency is not None:
            pieces.append(f"{latency}ms")
        detail = result.get("detail")
        if detail:
            pieces.append(str(detail))
        collection = result.get("collection")
        if collection:
            pieces.append(str(collection))
        info = f" ({', '.join(pieces)})" if pieces else ""
        lines.append(f"- `{name}`: *{status}*{info}")
    return "\n".join(lines)


@shared_task(name="health.monitor_lightmem")
def monitor_lightmem_health() -> Dict[str, Any]:
    """Poll LightMem health endpoints and alert on failures."""

    summary = lightmem_health_summary()
    logger.info("LightMem health summary: %s", summary)
    if not LIGHTMEM_HEALTH_ALERT_ENABLED:
        return summary

    status = summary.get("status")
    if status == "ok":
        return summary

    message = ":rotating_light: *LightMem health alert*\n" + _format_lightmem_health_markdown(summary)
    try:
        dispatch_notification(
            LIGHTMEM_HEALTH_ALERT_CHANNEL or "slack",
            message,
            targets=_LIGHTMEM_HEALTH_ALERT_TARGETS or None,
            metadata={
                "subject": f"LightMem health status: {status}",
                "markdown": message,
            },
        )
    except Exception as exc:  # pragma: no cover - alert best-effort
        logger.warning("Failed to dispatch LightMem health alert: %s", exc, exc_info=True)
    return summary


@shared_task(name="m1.seed_recent_filings", bind=True, max_retries=INGEST_TASK_MAX_RETRIES)
def seed_recent_filings_task(self, days_back: int = 1) -> int:
    logger.info("Running DART seeding task for the last %d day(s).", days_back)
    try:
        created = seed_recent_filings_job(days_back=days_back)
    except FatalIngestError as exc:
        _handle_ingest_exception(self, exc, payload={"days_back": days_back})
        raise
    except TransientIngestError as exc:
        _handle_ingest_exception(self, exc, payload={"days_back": days_back})
        raise
    except Exception as exc:
        _handle_ingest_exception(self, TransientIngestError(str(exc)), payload={"days_back": days_back})
        raise

    # Kick off event study ingest/aggregation asynchronously so the dashboard stays fresh.
    try:
        cast(Any, sync_stock_prices).delay(days_back=days_back + 5)
        cast(Any, sync_benchmark_prices).delay(days_back=days_back + 5)
        cast(Any, sync_security_metadata).delay(days_back=1)
        cast(Any, ingest_event_study_events).delay(days_back=days_back)
        cast(Any, update_event_study_returns).delay()
        cast(Any, aggregate_event_study_summary).delay()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to enqueue market/event study tasks after seeding: %s", exc, exc_info=True)

    return created


@shared_task(name="m1.process_filing", bind=True, max_retries=INGEST_TASK_MAX_RETRIES)
def process_filing(self, filing_id: str) -> str:
    db = _open_session()
    stage_results: List[StageResult] = []
    stage_started = time.perf_counter()
    filing: Optional[Filing] = None

    def _finish_stage(result: str) -> str:
        ingest_observe_latency(PROCESS_STAGE, time.perf_counter() - stage_started)
        ingest_record_result(PROCESS_STAGE, result)
        return result

    try:
        filing = db.query(Filing).filter(Filing.id == filing_id).one_or_none()
        if not filing:
            logger.error("Filing %s not found.", filing_id)
            return _finish_stage("missing")

        raw_content = cast(Optional[str], filing.raw_md) or ""
        existing_chunks = cast(Optional[Sequence[Any]], filing.chunks)
        chunk_count = len(existing_chunks or [])
        resolved_pdf_path: Optional[str] = None

        def run_stage(name: str, func: Callable[[], None], *, critical: bool) -> bool:
            try:
                func()
            except StageSkip as exc:
                db.rollback()
                logger.info(
                    "Filing %s stage '%s' skipped: %s",
                    filing.id,
                    name,
                    exc,
                )
                stage_results.append(
                    StageResult(name=name, critical=critical, success=False, error=str(exc), skipped=True)
                )
                return False
            except Exception as exc:
                db.rollback()
                level = logging.ERROR if critical else logging.WARNING
                logger.log(
                    level,
                    "Filing %s stage '%s' failed: %s",
                    filing.id,
                    name,
                    exc,
                    exc_info=True,
                )
                stage_results.append(
                    StageResult(name=name, critical=critical, success=False, error=str(exc))
                )
                return False

            stage_results.append(StageResult(name=name, critical=critical, success=True))
            return True

        def ingest_stage() -> None:
            nonlocal raw_content, chunk_count, resolved_pdf_path
            pdf_path = _ensure_pdf_path(filing)
            xml_paths = _load_xml_paths(filing)
            if not pdf_path and not xml_paths:
                logger.warning("Filing %s skipped: no PDF or XML sources available.", filing.id)
                raise StageSkip("No PDF or XML sources found for ingestion.")

            extracted: List[Dict[str, Any]] = []
            if pdf_path:
                resolved_pdf_path = pdf_path
                pdf_chunks = extract_chunks(pdf_path)
                extracted.extend(pdf_chunks)
                pdf_text_characters = _count_text_characters(pdf_chunks, source="pdf")
                if (
                    ocr_service.is_enabled()
                    and pdf_text_characters < _OCR_MIN_TEXT_LENGTH
                ):
                    if _OCR_ENABLE_LOG:
                        logger.info(
                            "Vision OCR fallback triggered for filing %s (pdf_text_chars=%d).",
                            filing.id,
                            pdf_text_characters,
                        )
                    try:
                        ocr_chunks = ocr_service.extract_text_chunks_from_pdf(
                            pdf_path,
                            max_pages=_OCR_PAGE_LIMIT,
                        )
                    except Exception as exc:  # pragma: no cover - external service
                        logger.warning(
                            "Vision OCR failed for filing %s: %s",
                            filing.id,
                            exc,
                            exc_info=True,
                        )
                    else:
                        if ocr_chunks:
                            extracted.extend(ocr_chunks)
                        elif _OCR_ENABLE_LOG:
                            logger.info(
                                "Vision OCR produced no text for filing %s.",
                                filing.id,
                            )
            if xml_paths:
                extracted.extend(extract_chunks_from_xml(xml_paths))
            if not extracted:
                logger.warning("Filing %s skipped: extraction yielded no chunks.", filing.id)
                raise StageSkip("No chunks could be extracted from the available sources.")

            raw_candidate = cast(Optional[str], filing.raw_md)
            raw_content = raw_candidate or raw_content
            chunk_count = len(extracted)
            table_chunks: List[Dict[str, Any]] = []

        def table_extraction_stage() -> None:
            nonlocal table_chunks
            pdf_path = resolved_pdf_path or _ensure_pdf_path(filing)
            if not pdf_path:
                raise StageSkip("No PDF available for table extraction.")
            try:
                stats = table_extraction_service.extract_tables_for_filing(
                    db,
                    filing=filing,
                    pdf_path=pdf_path,
                )
            except table_extraction_service.TableExtractionServiceError as exc:
                receipt_no = cast(Optional[str], filing.receipt_no)
                corp_code = cast(Optional[str], filing.corp_code)
                ticker = cast(Optional[str], filing.ticker)
                ingest_dlq_service.record_dead_letter(
                    db,
                    task_name="table_extraction",
                    payload={"filing_id": str(filing.id), "pdf_path": pdf_path},
                    error=str(exc),
                    retries=getattr(self.request, "retries", 0),
                    receipt_no=receipt_no,
                    corp_code=corp_code,
                    ticker=ticker,
                )
                raise
            else:
                logger.info(
                    "table_extraction.persisted",
                    extra={
                        "filing_id": str(filing.id),
                        "receipt_no": filing.receipt_no,
                        "stored": stats.get("stored"),
                        "deleted": stats.get("deleted"),
                        "elapsed_ms": stats.get("elapsed_ms"),
                    },
                )
                table_chunks = stats.get("chunks") or []

            run_stage("extract_tables", table_extraction_stage, critical=False)
            if table_chunks:
                extracted.extend(table_chunks)

            _save_chunks(filing, extracted, db, commit=False)
            vector_metadata = _build_vector_metadata(filing)
            vector_service.store_chunk_vectors(str(filing.id), extracted, metadata=vector_metadata)
            db.commit()

        def classification_stage() -> None:
            nonlocal raw_content
            if not raw_content.strip():
                raise RuntimeError("Empty filing content; classification is not possible.")

            classification = llm_service.classify_filing_content(raw_content)
            normalized_category = _normalize_category_label(classification.get("category"))
            _set_filing_fields(
                filing,
                category=normalized_category,
                category_confidence=classification.get("confidence_score"),
            )
            db.commit()

        def facts_stage() -> None:
            nonlocal raw_content
            if not raw_content.strip():
                raise RuntimeError("Empty filing content; fact extraction is not possible.")

            extraction_result = llm_service.extract_structured_info(raw_content)
            facts_payload = _normalize_facts(extraction_result.get("facts"))
            if not facts_payload:
                logger.info("No structured facts extracted for filing %s.", filing.id)
                return

            try:
                checked = llm_service.self_check_extracted_info(raw_content, facts_payload)
            except Exception as exc:
                logger.warning("Self-check failed for %s: %s", filing.id, exc, exc_info=True)
                normalized = facts_payload
            else:
                corrected = checked.get("corrected_json", {}).get("facts") or checked.get("corrected_json")
                normalized = _normalize_facts(corrected) if corrected else facts_payload

            _save_facts(filing, normalized, db)

        def summary_stage() -> None:
            nonlocal raw_content
            if not raw_content.strip():
                raise RuntimeError("Empty filing content; summary generation is not possible.")

            summary = llm_service.summarize_filing_content(raw_content)
            if not isinstance(summary, dict):
                raise RuntimeError("Summary payload is not a dictionary.")

            _save_summary(filing, summary, db)
            normalized_sentiment = _normalize_sentiment(
                summary.get("sentiment") or summary.get("sentiment_label")
            )
            if normalized_sentiment:
                try:
                    vector_service.update_filing_metadata(
                        str(filing.id),
                        {
                            "sentiment": normalized_sentiment,
                            "sentiment_reason": summary.get("sentiment_reason"),
                        },
                    )
                except Exception as exc:  # pragma: no cover - external dependency
                    logger.warning(
                        "Vector metadata update failed for filing %s during summary stage: %s",
                        filing.id,
                        exc,
                        exc_info=True,
                    )
            if TELEGRAM_NOTIFY_POS_NEG_ONLY and normalized_sentiment not in {"positive", "negative"}:
                logger.info(
                    "Telegram alert skipped for %s (sentiment=%s)",
                    filing.id,
                    normalized_sentiment or summary.get("sentiment"),
                )
                return
            message = _format_notification(filing, summary)
            try:
                send_telegram_alert(message)
            except Exception as exc:
                logger.warning("Telegram alert failed for %s: %s", filing.id, exc, exc_info=True)

        ingest_success = run_stage("ingest_chunks", ingest_stage, critical=True)

        if ingest_success:
            run_stage("classify_category", classification_stage, critical=False)
            run_stage("extract_facts", facts_stage, critical=False)
            run_stage("summarize_and_notify", summary_stage, critical=False)

        def _result_label(result: StageResult) -> str:
            if result.success:
                return "ok"
            if result.skipped:
                return "skip"
            return "fail"

        stage_summary = ", ".join(
            f"{result.name}={_result_label(result)}" for result in stage_results
        ) or "no stages executed"
        logger.info(
            "Filing %s processing summary (chunks=%s): %s",
            filing.id,
            chunk_count,
            stage_summary,
        )

        skipped_results = [result for result in stage_results if result.skipped]
        critical_failures = [
            result for result in stage_results if result.critical and not result.success and not result.skipped
        ]
        non_critical_failures = [result for result in stage_results if not result.success and not result.skipped]

        if skipped_results:
            _set_filing_fields(filing, status=STATUS_PARTIAL, analysis_status=ANALYSIS_PARTIAL)
            db.commit()
            return _finish_stage("skipped")

        if critical_failures:
            _set_filing_fields(filing, status=STATUS_FAILED, analysis_status=ANALYSIS_FAILED)
            db.commit()
            return _finish_stage("failed")

        if non_critical_failures:
            _set_filing_fields(filing, status=STATUS_PARTIAL, analysis_status=ANALYSIS_PARTIAL)
            db.commit()
            return _finish_stage("partial")

        _set_filing_fields(filing, status=STATUS_COMPLETED, analysis_status=ANALYSIS_ANALYZED)
        db.commit()
        return _finish_stage("completed")

    except Exception as exc:
        db.rollback()
        ingest_record_error(PROCESS_STAGE, "task", exc)
        logger.error("Error processing filing %s: %s", filing_id, exc, exc_info=True)
        _finish_stage("failure")
        _retry_or_dead_letter(self, db=db, filing_id=filing_id, filing=filing, exc=exc)
        raise
    finally:
        db.close()


def tally_news_window(
    signals: Iterable[NewsSignal],
    window_start: datetime,
    window_end: datetime,
    *,
    topics_limit: int,
    neutral_threshold: float,
) -> Dict[str, Any]:
    """Aggregate sentiment statistics for a window of news signals."""
    summary = summarize_news_signals(signals, neutral_threshold=neutral_threshold)
    top_topics = build_top_topics(summary.topic_counts, topics_limit)

    return {
        "window_start": window_start,
        "window_end": window_end,
        "article_count": summary.article_count,
        "positive_count": summary.positive_count,
        "neutral_count": summary.neutral_count,
        "negative_count": summary.negative_count,
        "avg_sentiment": summary.avg_sentiment,
        "min_sentiment": summary.min_sentiment,
        "max_sentiment": summary.max_sentiment,
        "top_topics": top_topics,
    }


def _build_news_alert(metrics: Dict[str, Any]) -> str:
    lines = [
        "*[Market Mood]*",
        f"Window (UTC): {metrics['window_start'].isoformat()} -> {metrics['window_end'].isoformat()}",
        (
            f"Articles {metrics['article_count']} | "
            f"+:{metrics['positive_count']} ~:{metrics['neutral_count']} -:{metrics['negative_count']}"
        ),
    ]
    if metrics.get("avg_sentiment") is not None:
        lines.append(
            "Sentiment avg "
            f"{metrics['avg_sentiment']:.2f} "
            f"(min {metrics['min_sentiment']:.2f}, max {metrics['max_sentiment']:.2f})"
        )
    if metrics.get("top_topics"):
        topic_text = ", ".join(
            f"{topic['topic']} ({topic['count']})" for topic in metrics["top_topics"]
        )
        lines.append(f"Top topics: {topic_text}")
    lines.append("_(For information only. This is not investment advice.)_")
    return "\n".join(lines)


@shared_task(name="m2.process_news")
def process_news_article(article_payload: Any) -> str:
    """Analyse a single news article and persist its sentiment signal."""
    if isinstance(article_payload, NewsArticleCreate):
        article = article_payload
    else:
        try:
            article = NewsArticleCreate(**article_payload)
        except ValidationError as exc:
            logger.error("Invalid news article payload: %s", exc)
            return "invalid"

    db = _open_session()
    try:
        existing = db.query(NewsSignal).filter(NewsSignal.url == article.url).one_or_none()
        if existing:
            logger.info("News article already processed: %s", article.url)
            return str(existing.id)

        analysis = llm_service.analyze_news_article(article.original_text)
        if analysis.get("error"):
            logger.warning(
                "Skipping news article %s due to analysis error: %s",
                article.url,
                analysis.get("details") or analysis.get("error"),
            )
            return "analysis_error"

        validated = analysis if analysis.get("validated") else llm_service.validate_news_analysis_result(analysis)
        if validated.get("error"):
            logger.warning(
                "Skipping news article %s due to validation error: %s",
                article.url,
                validated.get("details") or validated.get("error"),
            )
            return "analysis_error"

        sentiment = validated.get("sentiment")
        topics = validated.get("topics") or []
        sanitized_rationale = sanitize_news_summary(
            validated.get("rationale"),
            max_chars=max(160, NEWS_SUMMARY_MAX_CHARS),
        )
        evidence = {"rationale": sanitized_rationale} if sanitized_rationale else None

        reliability = score_source_reliability(article.source, article.url)
        sanitized_summary = sanitize_news_summary(
            article.summary,
            max_chars=max(120, NEWS_SUMMARY_MAX_CHARS),
        )

        resolved_ticker = article.ticker
        if not resolved_ticker:
            resolved_ticker = resolve_news_ticker(
                db,
                headline=article.headline,
                summary=sanitized_summary,
                body=(article.original_text[:4000] if getattr(article, "original_text", None) else None),
                topics=topics,
            )

        news_signal = NewsSignal(
            ticker=resolved_ticker,
            source=article.source,
            url=article.url,
            headline=article.headline,
            summary=sanitized_summary,
            license_type=article.license_type,
            license_url=article.license_url,
            published_at=article.published_at,
            sentiment=sentiment,
            topics=topics,
            evidence=evidence,
            source_reliability=reliability,
        )
        db.add(news_signal)
        db.flush()
        try:
            assign_article_to_sector(db, news_signal)
        except Exception as exc:
            logger.warning("Failed to assign sector for news signal %s: %s", article.url, exc, exc_info=True)
        db.commit()
        if sanitized_rationale:
            _store_news_vector_entry(
                news_signal,
                chunk_text=sanitized_rationale,
                topics=topics,
                sentiment_score=sentiment,
                reliability=reliability,
            )
        else:
            logger.debug("News article %s skipped for vector store due to empty rationale.", article.url)
        logger.info("Stored news signal %s for %s", news_signal.id, article.url)
        return str(news_signal.id)

    except Exception as exc:
        db.rollback()
        logger.error("Error processing news article %s: %s", getattr(article, "url", "unknown"), exc, exc_info=True)
        return "error"
    finally:
        db.close()


@shared_task(name="m2.seed_news_feeds", bind=True, max_retries=INGEST_TASK_MAX_RETRIES)
def seed_news_feeds(self, limit_per_feed: Optional[int] = None, use_mock_fallback: bool = False) -> int:
    """Fetch latest news articles and enqueue them for processing."""
    fetch_limit = max(1, int(limit_per_feed or NEWS_FETCH_LIMIT))
    queued = 0

    try:
        articles = fetch_news_batch(limit_per_feed=fetch_limit, use_mock_fallback=use_mock_fallback)
    except FatalIngestError as exc:
        _handle_ingest_exception(
            self,
            exc,
            payload={"limit_per_feed": fetch_limit, "use_mock_fallback": use_mock_fallback},
        )
        raise
    except TransientIngestError as exc:
        _handle_ingest_exception(
            self,
            exc,
            payload={"limit_per_feed": fetch_limit, "use_mock_fallback": use_mock_fallback},
        )
        raise
    except Exception as exc:
        _handle_ingest_exception(
            self,
            TransientIngestError(str(exc)),
            payload={"limit_per_feed": fetch_limit, "use_mock_fallback": use_mock_fallback},
        )
        raise

    if not articles:
        logger.info("No news articles fetched from feeds.")
        return queued

    for article in articles:
        try:
            payload = article.model_dump() if hasattr(article, "model_dump") else dict(article)
            cast(Any, process_news_article).delay(payload)
            queued += 1
        except Exception as exc:
            logger.warning(
                "Failed to enqueue news article '%s': %s",
                getattr(article, "headline", ""),
                exc,
                exc_info=True,
            )

    logger.info("Queued %d news article(s) for processing (limit_per_feed=%d).", queued, fetch_limit)
    return queued


@shared_task(name="m2.aggregate_news")
def aggregate_news_data(window_end_iso: Optional[str] = None) -> str:
    """Aggregate news sentiment metrics for the latest window."""
    try:
        if window_end_iso:
            reference_time = datetime.fromisoformat(window_end_iso)
            if reference_time.tzinfo is None:
                reference_time = reference_time.replace(tzinfo=timezone.utc)
            else:
                reference_time = reference_time.astimezone(timezone.utc)
        else:
            reference_time = datetime.now(timezone.utc)
    except ValueError:
        logger.warning("Invalid window_end_iso='%s'. Using current time.", window_end_iso)
        reference_time = datetime.now(timezone.utc)

    window_minutes = env_int("NEWS_AGGREGATION_MINUTES", 15, minimum=5)
    neutral_threshold = env_float("NEWS_NEUTRAL_THRESHOLD", 0.15, minimum=0.0)
    topics_limit = env_int("NEWS_TOPICS_LIMIT", 5, minimum=1)

    window_end = reference_time.replace(second=0, microsecond=0)
    offset = window_end.minute % window_minutes
    if offset:
        window_end = window_end - timedelta(minutes=offset)
    window_start = window_end - timedelta(minutes=window_minutes)

    db = _open_session()
    try:
        signals = (
            db.query(NewsSignal)
            .filter(NewsSignal.published_at >= window_start, NewsSignal.published_at < window_end)
            .order_by(NewsSignal.published_at.asc())
            .all()
        )

        metrics = tally_news_window(
            signals,
            window_start,
            window_end,
            topics_limit=topics_limit,
            neutral_threshold=neutral_threshold,
        )

        tickers: set[str] = set()
        for signal in signals:
            ticker_value = cast(Optional[str], getattr(signal, "ticker", None))
            if ticker_value:
                tickers.add(ticker_value)

        record = (
            db.query(NewsObservation)
            .filter(NewsObservation.window_start == metrics["window_start"])
            .one_or_none()
        )
        if not record:
            record = NewsObservation(
                window_start=metrics["window_start"],
                window_end=metrics["window_end"],
            )
            db.add(record)

        record.article_count = metrics["article_count"]
        record.positive_count = metrics["positive_count"]
        record.neutral_count = metrics["neutral_count"]
        record.negative_count = metrics["negative_count"]
        record.avg_sentiment = metrics["avg_sentiment"]
        record.min_sentiment = metrics["min_sentiment"]
        record.max_sentiment = metrics["max_sentiment"]
        record.top_topics = metrics["top_topics"]

        db.commit()

        try:
            for window_days in (7, 30):
                compute_news_window_metrics(
                    db=db,
                    window_end=metrics["window_end"],
                    window_days=window_days,
                    scope="global",
                    ticker=None,
                )
                for ticker in tickers:
                    compute_news_window_metrics(
                        db=db,
                        window_end=metrics["window_end"],
                        window_days=window_days,
                        scope="ticker",
                        ticker=ticker,
                    )
        except Exception as exc:  # pragma: no cover - resilience
            logger.warning("Failed to compute extended news window metrics: %s", exc, exc_info=True)

        if metrics["article_count"] > 0:
            message = _build_news_alert(metrics)
            send_telegram_alert(message)

        logger.info(
            "Aggregated Market Mood window %s - articles=%d",
            metrics["window_start"],
            metrics["article_count"],
        )
        return metrics["window_start"].isoformat()

    except Exception as exc:
        db.rollback()
        logger.error("Error aggregating news metrics: %s", exc, exc_info=True)
        return "error"
    finally:
        db.close()


@shared_task(name="m2.cleanup_news_signals")
def cleanup_news_signals(retention_days: Optional[int] = None) -> Dict[str, Union[int, str]]:
    """Purge news signals and related aggregates older than the retention window."""

    days = int(retention_days or NEWS_RETENTION_DAYS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    db = _open_session()
    try:
        deleted_signals = (
            db.query(NewsSignal).filter(NewsSignal.published_at < cutoff).delete(synchronize_session=False)
        )
        deleted_observations = (
            db.query(NewsObservation).filter(NewsObservation.window_end < cutoff).delete(synchronize_session=False)
        )
        deleted_windows = (
            db.query(NewsWindowAggregate)
            .filter(NewsWindowAggregate.computed_for < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            "Cleaned news data older than %s: signals=%d observations=%d windows=%d",
            cutoff,
            deleted_signals,
            deleted_observations,
            deleted_windows,
        )
        return {
            "deleted_signals": int(deleted_signals),
            "deleted_observations": int(deleted_observations),
            "deleted_window_metrics": int(deleted_windows),
            "cutoff": cutoff.isoformat(),
        }
    except Exception as exc:
        db.rollback()
        logger.error("Failed to cleanup news data older than %d days: %s", days, exc, exc_info=True)
        return {
            "deleted_signals": 0,
            "deleted_observations": 0,
            "deleted_window_metrics": 0,
            "error": str(exc),
        }
    finally:
        db.close()


@shared_task(name="m2.aggregate_sector_daily")
def aggregate_sector_daily(hours_back: int = 36) -> str:
    """Compute sector daily metrics for the recent horizon (default 36h)."""
    now_local = datetime.now(SECTOR_ZONE)
    start_local = now_local - timedelta(hours=max(1, hours_back))
    start_day = start_local.date()
    end_day = now_local.date()

    db = _open_session()
    try:
        metrics = compute_sector_daily_metrics(db, start_day, end_day)
        db.commit()
        logger.info(
            "Aggregated %d sector daily metric rows for %s -> %s",
            len(metrics),
            start_day.isoformat(),
            end_day.isoformat(),
        )
        return str(len(metrics))
    except Exception as exc:
        db.rollback()
        logger.error("Sector daily aggregation failed: %s", exc, exc_info=True)
        raise
    finally:
        db.close()


@shared_task(name="m2.aggregate_sector_windows")
def aggregate_sector_windows(as_of_iso: Optional[str] = None, window_days: Sequence[int] = (7, 30, 90)) -> str:
    """Compute rolling sector metrics (hotspot + sparkline)."""
    if as_of_iso:
        try:
            as_of_day = datetime.fromisoformat(as_of_iso).date()
        except ValueError:
            logger.warning("Invalid as_of_iso %s. Falling back to current date.", as_of_iso)
            as_of_day = datetime.now(SECTOR_ZONE).date()
    else:
        as_of_day = datetime.now(SECTOR_ZONE).date()

    db = _open_session()
    try:
        records = compute_sector_window_metrics(db, as_of_day, window_days=window_days)
        db.commit()
        logger.info(
            "Aggregated %d sector window metric rows for %s (windows=%s)",
            len(records),
            as_of_day.isoformat(),
            ",".join(str(item) for item in window_days),
        )
        return str(len(records))
    except Exception as exc:
        db.rollback()
        logger.error("Sector window aggregation failed: %s", exc, exc_info=True)
        raise
    finally:
        db.close()


def _parse_reference_date(target_date_iso: Optional[str]) -> date:
    if target_date_iso:
        try:
            parsed = datetime.fromisoformat(target_date_iso)
            if isinstance(parsed, datetime):
                return parsed.date()
        except ValueError:
            try:
                return date.fromisoformat(target_date_iso)
            except ValueError:
                logger.warning("Invalid target_date_iso '%s'. Using current KST date.", target_date_iso)
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


@shared_task(name="m4.cleanup_daily_briefs")
def cleanup_daily_briefs(retention_days: int = 30) -> Dict[str, int]:
    """Cleanup stale daily brief artifacts (local + storage)."""

    db = SessionLocal()
    try:
        result = cleanup_daily_brief_artifacts(retention_days=retention_days, session=db)
        logger.info("Cleaned up daily briefs older than %d days: %s", retention_days, result)
        return result
    finally:
        db.close()


@shared_task(name="m4.generate_daily_brief")
def generate_daily_brief(
    target_date_iso: Optional[str] = None,
    compile_pdf: bool = True,
    force: bool = False,
) -> str:
    """Render the daily LaTeX brief and persist generation audit logs."""

    reference_date = _parse_reference_date(target_date_iso)
    db = SessionLocal()
    try:
        if not force and has_brief_been_generated(db, reference_date=reference_date, channel=DAILY_BRIEF_CHANNEL):
            logger.info("Daily brief already generated for %s.", reference_date.isoformat())
            return "already_generated"

        payload = build_daily_brief_payload(reference_date=reference_date, session=db)
        output_dir = DAILY_BRIEF_OUTPUT_ROOT / reference_date.isoformat()
        tex_name = f"daily_brief_{reference_date.isoformat()}.tex"
        render_result = render_daily_brief_document(
            payload=payload,
            reference_date=reference_date,
            output_dir=output_dir,
            tex_name=tex_name,
            compile_pdf=compile_pdf,
            session=db,
        )
        record_brief_generation(db, reference_date=reference_date, channel=DAILY_BRIEF_CHANNEL)

        outputs = render_result["outputs"]
        pdf_path = outputs.get("pdf")
        final_path = pdf_path or outputs.get("tex")
        if final_path is None:
            final_path = output_dir / tex_name
        logger.info("Daily brief generated for %s (output=%s).", reference_date.isoformat(), final_path)
        return str(final_path)
    except Exception as exc:
        db.rollback()
        logger.error("Daily brief generation failed for %s: %s", reference_date.isoformat(), exc, exc_info=True)
        raise
    finally:
        db.close()


def _flatten_citation_entries(meta: Mapping[str, Any]) -> List[str]:
    if not isinstance(meta, dict):
        return []
    collected: List[str] = []
    citation_map = meta.get("citations")
    if isinstance(citation_map, dict):
        for value in citation_map.values():
            if isinstance(value, list):
                collected.extend(str(item) for item in value if item)
    retrieval = meta.get("retrieval")
    if isinstance(retrieval, dict):
        doc_ids = retrieval.get("doc_ids")
        if isinstance(doc_ids, list):
            collected.extend(str(item) for item in doc_ids if item)
    return collected


def _build_transcript_payload(messages: List[ChatMessage]) -> List[Dict[str, str]]:
    payload: List[Dict[str, str]] = []
    for message in messages:
        content = cast(Optional[str], message.content)
        role = cast(Optional[str], message.role)
        if not content:
            continue
        payload.append({"role": role or "", "content": content})
    return payload


@shared_task(name="m5.summarize_chat_session")
def summarize_chat_session(session_id: str) -> str:
    """Generate a condensed summary for a chat session and archive older turns."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        return "invalid_session_id"

    db = _open_session()
    try:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_uuid, ChatSession.archived_at.is_(None))
            .with_for_update()
            .first()
        )
        if session is None:
            return "session_missing"

        raw_snapshot = session.memory_snapshot
        snapshot: Dict[str, Any] = {}
        if isinstance(raw_snapshot, Mapping):
            snapshot = dict(raw_snapshot)
        summarized_until = int(snapshot.get("summarized_until") or 0)

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_uuid)
            .order_by(ChatMessage.seq.asc())
            .all()
        )
        if not messages:
            return "no_messages"

        def _coerce_seq_value(chat_message: ChatMessage) -> int:
            return int(cast(Any, getattr(chat_message, "seq", 0) or 0))

        unsummarized = [message for message in messages if _coerce_seq_value(message) > summarized_until]
        keep_count = SUMMARY_RECENT_TURNS * 2
        if len(unsummarized) <= keep_count:
            return "insufficient_history"
        if len(unsummarized) < SUMMARY_TRIGGER_MESSAGES:
            return "below_threshold"

        archive_candidates = unsummarized[:-keep_count]
        transcript = _build_transcript_payload(archive_candidates)
        if not transcript:
            return "insufficient_history"

        try:
            summary_text = llm_service.summarize_chat_transcript(transcript)
        except Exception as exc:  # pragma: no cover - summariser best-effort
            logger.error("Chat summary failed for %s: %s", session_uuid, exc, exc_info=True)
            db.rollback()
            return "summary_failed"

        citations: List[str] = []
        for message in archive_candidates:
            meta_payload = message.meta if isinstance(message.meta, Mapping) else {}
            citations.extend(_flatten_citation_entries(meta_payload))
        unique_citations = sorted({item for item in citations if item})

        snapshot_payload: Dict[str, Any] = dict(snapshot)
        snapshot_payload["summary"] = summary_text
        snapshot_payload["citations"] = unique_citations
        last_seq_value = _coerce_seq_value(archive_candidates[-1])
        snapshot_payload["summarized_until"] = last_seq_value
        snapshot_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        session_proxy = cast(Any, session)
        session_proxy.memory_snapshot = snapshot_payload
        if summary_text:
            session_proxy.summary = chat_service.trim_preview(summary_text)

        max_seq = last_seq_value
        archived = chat_service.archive_chat_messages(db, session_id=session_uuid, seq_threshold=max_seq)
        db.commit()
        logger.info(
            "Summarised chat session %s up to seq %d (archived=%d)",
            session_uuid,
            max_seq,
            archived,
        )
        return "summarized"
    except Exception as exc:
        db.rollback()
        logger.error("Chat summarisation error for %s: %s", session_id, exc, exc_info=True)
        return "error"
    finally:
        db.close()


def _summarize_rag_result(
    question: str,
    context_chunks: Iterable[Dict[str, Any]],
    answer_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Produce a compact summary of a RAG answer for observability."""
    context_list = list(context_chunks)
    warnings = list(answer_result.get("warnings") or [])
    citations = dict(answer_result.get("citations") or {})
    answer_text = str(answer_result.get("answer") or "")

    return {
        "question": question,
        "context_size": len(context_list),
        "answer_length": len(answer_text),
        "citations": citations,
        "warnings": warnings,
        "error": answer_result.get("error"),
        "model_used": answer_result.get("model_used"),
    }


@shared_task(name="m3.run_rag_self_check")
def run_rag_self_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist lightweight telemetry for RAG responses (Langfuse + logs)."""
    question = payload.get("question", "")
    filing_id = payload.get("filing_id")
    answer_result = payload.get("answer") or {}
    context_chunks = payload.get("context") or []
    trace_id = payload.get("trace_id")

    summary = _summarize_rag_result(question, context_chunks, answer_result)
    summary["filing_id"] = filing_id
    summary["trace_id"] = trace_id

    if llm_service.LANGFUSE_CLIENT:
        try:
            trace = llm_service.LANGFUSE_CLIENT.trace(
                name="rag_self_check",
                metadata={"filing_id": filing_id, "trace_id": trace_id},
            )
            trace.generation(
                name="rag_summary",
                model=str(summary.get("model_used") or ""),
                input=question[:2000],
                output=str(summary)[:2000],
            )
            llm_service.LANGFUSE_CLIENT.flush()
        except Exception as exc:  # pragma: no cover - observability best-effort
            logger.debug("Langfuse RAG summary logging skipped: %s", exc, exc_info=True)

    logger.info(
        "RAG summary (filing=%s, trace=%s): context=%d warnings=%d error=%s",
        filing_id,
        trace_id,
        summary["context_size"],
        len(summary["warnings"]),
        summary.get("error"),
    )
    return summary


@shared_task(name="memory.promote_long_term")
def promote_long_term_memory() -> Dict[str, Any]:
    """Nightly job that promotes STM summaries into the long-term memory store."""

    try:
        persisted = run_long_term_update()
        logger.info("Promoted %d session summaries into long-term memory.", persisted)
        return {"persisted": persisted}
    except Exception as exc:  # pragma: no cover - best-effort promotion
        logger.error("LightMem long-term promotion failed: %s", exc, exc_info=True)
        return {"error": str(exc)}


@shared_task(name="m3.snapshot_evidence_diff")
def snapshot_evidence_diff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist evidence snapshots for diff tracking."""
    db = SessionLocal()
    stored: List[Dict[str, Any]] = []
    evidence_items = payload.get("evidence") or []
    author = payload.get("author")
    process = payload.get("process") or "api.rag"
    trace_id = payload.get("trace_id")
    owner_org_id = _safe_uuid(payload.get("org_id"))
    owner_user_id = _safe_uuid(payload.get("user_id"))

    try:
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            urn_id = item.get("urn_id")
            snapshot = save_evidence_snapshot(
                db,
                urn_id=str(urn_id or ""),
                payload=item,
                author=author,
                process=process,
                org_id=owner_org_id,
                user_id=owner_user_id,
            )
            if snapshot:
                stored.append(
                    {
                        "urn_id": snapshot.urn_id,
                        "snapshot_hash": snapshot.snapshot_hash,
                        "diff_type": snapshot.diff_type,
                    }
                )
        db.commit()
        logger.info(
            "Evidence diff snapshots stored (trace=%s, count=%d).",
            trace_id,
            len(stored),
        )
        return {"stored": stored, "trace_id": trace_id}
    except Exception as exc:  # pragma: no cover - best-effort persistence
        db.rollback()
        logger.warning("Failed to snapshot evidence diff (trace=%s): %s", trace_id, exc, exc_info=True)
        return {"stored": stored, "trace_id": trace_id, "error": str(exc)}
    finally:
        db.close()


@shared_task(name="market_data.sync_stock_prices", bind=True, max_retries=INGEST_TASK_MAX_RETRIES)
def sync_stock_prices(self, days_back: int = 7) -> Dict[str, Any]:
    """Fetch recent stock prices from the public API and upsert into the price table."""

    start_date = date.today() - timedelta(days=days_back)
    end_date = date.today()
    db = SessionLocal()
    try:
        inserted = market_data_service.ingest_stock_prices(
            db,
            start_date=start_date,
            end_date=end_date,
        )
        logger.info("Synced %d stock price rows (%s~%s).", inserted, start_date, end_date)
        return {"rows": inserted}
    except FatalIngestError as exc:
        _handle_ingest_exception(
            self,
            exc,
            payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
        raise
    except TransientIngestError as exc:
        _handle_ingest_exception(
            self,
            exc,
            payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
        raise
    except Exception as exc:
        _handle_ingest_exception(
            self,
            TransientIngestError(str(exc)),
            payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
        raise
    finally:
        db.close()


@shared_task(name="market_data.sync_benchmark_prices", bind=True, max_retries=INGEST_TASK_MAX_RETRIES)
def sync_benchmark_prices(self, days_back: int = 7) -> Dict[str, Any]:
    """Fetch benchmark ETF prices for market-model estimation."""

    start_date = date.today() - timedelta(days=days_back)
    end_date = date.today()
    db = SessionLocal()
    try:
        inserted = market_data_service.ingest_etf_prices(
            db,
            start_date=start_date,
            end_date=end_date,
        )
        logger.info("Synced %d benchmark price rows (%s~%s).", inserted, start_date, end_date)
        return {"rows": inserted}
    except FatalIngestError as exc:
        _handle_ingest_exception(
            self,
            exc,
            payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "type": "etf"},
        )
        raise
    except TransientIngestError as exc:
        _handle_ingest_exception(
            self,
            exc,
            payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "type": "etf"},
        )
        raise
    except Exception as exc:
        _handle_ingest_exception(
            self,
            TransientIngestError(str(exc)),
            payload={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "type": "etf"},
        )
        raise
    finally:
        db.close()


@shared_task(name="market_data.sync_security_metadata")
def sync_security_metadata(days_back: int = 1) -> Dict[str, Any]:
    """Refresh security metadata (market cap, buckets) and backfill events."""

    target_date = date.today() - timedelta(days=days_back - 1)
    db = SessionLocal()
    try:
        upserted = security_metadata_service.sync_security_metadata(db, as_of=target_date)
        updated = security_metadata_service.backfill_event_cap_metadata(db)
        logger.info("Synced %d security metadata rows; backfilled %d events.", upserted, updated)
        return {"rows": upserted, "events_updated": updated}
    except security_metadata_service.SecurityMetadataError as exc:
        logger.warning("Security metadata sync failed: %s", exc)
        return {"rows": 0, "error": str(exc)}
    finally:
        db.close()


@shared_task(name="event_study.ingest_events")
def ingest_event_study_events(days_back: int = 1) -> Dict[str, int]:
    """Normalize recent filings into event records."""

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    db = SessionLocal()
    try:
        created = event_study_service.ingest_events_from_filings(
            db,
            start_date=start_date,
            end_date=end_date,
        )
    finally:
        db.close()

    logger.info("Event study ingest completed: %d events.", created)
    return {"events": created}


@shared_task(name="event_study.update_returns")
def update_event_study_returns() -> Dict[str, int]:
    """Compute AR/CAR series for events lacking measurements."""

    db = SessionLocal()
    try:
        created = event_study_service.update_event_study_series(db)
    finally:
        db.close()

    logger.info("Event study AR/CAR update inserted %d rows.", created)
    return {"rows": created}


@shared_task(name="event_study.aggregate_summary")
def aggregate_event_study_summary() -> Dict[str, int]:
    """Aggregate cohort-level AAR/CAAR statistics."""

    db = SessionLocal()
    try:
        summaries = event_study_service.aggregate_event_summaries(
            db,
            as_of=date.today(),
        )
    finally:
        db.close()

    logger.info("Event study summary aggregation completed: %d rows.", summaries)
    return {"summaries": summaries}


@shared_task(name="tables.extract_receipt", bind=True, max_retries=INGEST_TASK_MAX_RETRIES)
def extract_tables_for_receipt(self, receipt_no: str) -> Dict[str, Any]:
    """Backfill normalized tables for a specific DART receipt number."""

    db = _open_session()
    try:
        result = table_extraction_service.run_table_extraction_for_receipt(db, receipt_no)
        logger.info(
            "tables.extract.completed",
            extra={"receipt_no": receipt_no, "stored": result.get("stored"), "elapsed_ms": result.get("elapsed_ms")},
        )
        return {"receipt_no": receipt_no, **result}
    except table_extraction_service.TableExtractionServiceError as exc:
        db.rollback()
        ingest_dlq_service.record_dead_letter(
            db,
            task_name="tables.extract",
            payload={"receipt_no": receipt_no},
            error=str(exc),
            retries=getattr(self.request, "retries", 0),
            receipt_no=receipt_no,
        )
        logger.error("tables.extract.failed receipt=%s error=%s", receipt_no, exc)
        return {"receipt_no": receipt_no, "error": str(exc)}
    finally:
        db.close()


@shared_task(name="rag.grid.run_job")
def run_rag_grid_job(job_id: str) -> None:
    """Initialize and dispatch an asynchronous QA grid job."""
    rag_grid.start_grid_job(job_id)


@shared_task(name="rag.grid.process_cell")
def process_rag_grid_cell(cell_id: str) -> None:
    """Execute a single QA grid cell."""
    rag_grid.process_grid_cell(cell_id)


@shared_task(name="compliance.cleanup_data_retention")
def cleanup_data_retention_job() -> Dict[str, int]:
    """Cron-friendly entry point for data retention policies."""
    stats = apply_retention_policies()
    logger.info("compliance.cleanup_data_retention completed: %s", stats)
    return stats


@shared_task(name="compliance.process_dsar_queue")
def process_dsar_queue(limit: int = 5) -> Dict[str, int]:
    """Background worker that processes pending DSAR requests."""
    stats = dsar_service.process_pending_requests(limit=limit)
    logger.info("compliance.process_dsar_queue processed: %s", stats)
    return stats
