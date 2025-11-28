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
from models.user import User
from models.filing import Filing
from models.news import NewsSignal
from models.proactive_notification import ProactiveNotification
from parse.pdf_parser import extract_chunks
from parse.xml_parser import extract_chunks_from_xml
from schemas.news import NewsArticleCreate
from services import (
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
    rag_grid,
    snapshot_service,
    market_stats_cache_service,
    event_study_service,
    focus_score_service,
)
from services.evidence_service import save_evidence_snapshot
from services.ingest_errors import FatalIngestError, TransientIngestError
from services.aggregation.sector_classifier import assign_article_to_sector
from services.aggregation.sector_metrics import compute_sector_daily_metrics, compute_sector_window_metrics
from services.aggregation.news_metrics import compute_news_window_metrics
from services.notification_service import dispatch_notification
from services.reliability.source_reliability import score_article as score_source_reliability
from services.aggregation.news_statistics import summarize_news_signals, build_top_topics
from services.embedding_utils import EMBEDDING_MODEL, embed_texts
from services.memory.facade import MEMORY_SERVICE
from services.user_settings_service import read_user_proactive_settings, read_user_lightmem_settings
from services.lightmem_config import default_user_id as lightmem_default_user_id
from services import proactive_service, user_profile_service
from services import proactive_briefing_service



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
DIGEST_CHANNEL = "slack"
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
    """Warm the recommendation cache by scanning recent filings."""

    with SessionLocal() as db:
        try:
            count = recommendation_service.refresh_cache(db)
            logger.info("Refreshed recommendation filings cache: %d items", count)
            return {"count": count}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to refresh recommendation cache: %s", exc, exc_info=True)
            return {"count": 0, "error": str(exc)}


@shared_task(name="lightmem.cleanup_profile_cache")
def cleanup_profile_cache() -> Dict[str, int]:
    """Placeholder for periodic cleanup of expired profile summaries (in-memory mode)."""
    # In Redis mode, TTL is handled automatically. For in-memory fallback, purge expired keys.
    cleaned = 0
    try:
        from services.memory.session_store import build_default_store

        store = build_default_store()
        store.purge_expired()
        cleaned = len(list(store.iter_session_ids()))
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Profile cache cleanup skipped: %s", exc)
    return {"cleaned": cleaned}


def _round_vec(vec: List[float], ndigits: int = 6) -> List[float]:
    return [round(float(x), ndigits) for x in vec]


def _maybe_memory_hint(user_id: uuid.UUID, query: str) -> Optional[str]:
    """Best-effort LightMem recall for proactive notifications."""
    if not query or not query.strip():
        return None
    try:
        records = MEMORY_SERVICE.retrieve_long_term(
            tenant_id=str(user_id),
            user_id=str(user_id),
            query=query,
            limit=1,
        )
    except Exception as exc:  # pragma: no cover - external store might fail
        logger.debug("LightMem hint lookup failed for user %s: %s", user_id, exc, exc_info=True)
        return None
    if not records:
        return None
    record = records[0]
    topic = (record.topic or "").strip()
    summary = (record.summary or "").strip()
    if summary and topic:
        return f"{topic}: {summary}"
    return summary or topic or None


def _attach_memory_hint(summary: Optional[str], hint: Optional[str], *, max_chars: int = 480) -> Optional[str]:
    """Append memory hint onto summary while keeping length bounded."""
    if not hint:
        return summary
    parts = [part.strip() for part in [summary or "", f"기억 메모: {hint}"] if part and part.strip()]
    combined = " · ".join(parts)
    if len(combined) <= max_chars:
        return combined
    trimmed = combined[:max_chars].rsplit(" ", 1)[0] or combined[:max_chars]
    return trimmed


@shared_task(name="proactive.scan", bind=True, max_retries=1)
def scan_proactive_notifications(self, window_minutes: int = 15) -> Dict[str, int]:
    """Scan recent filings/news and upsert proactive notifications based on user interest tags."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    db = SessionLocal()
    created = 0
    matched = 0
    doc_vectors_filings: Dict[str, List[float]] = {}
    doc_vectors_news: Dict[str, List[float]] = {}
    try:
        users = db.query(User.id).all()
        # preload recent filings/news
        recent_filings = (
            db.query(Filing)
            .filter(Filing.filed_at.isnot(None))
            .filter(Filing.filed_at >= window_start)
            .order_by(Filing.filed_at.desc())
            .all()
        )
        recent_news = (
            db.query(NewsSignal)
            .filter(NewsSignal.detected_at >= window_start)
            .order_by(NewsSignal.detected_at.desc())
            .all()
        )
        # Precompute document embeddings once per scan for efficiency
        filing_corpus = []
        filing_keys = []
        for filing in recent_filings:
            text = " ".join(
                part
                for part in [
                    filing.title,
                    filing.report_name,
                    filing.corp_name,
                    filing.ticker,
                    getattr(filing, "summary", None),
                ]
                if part
            )
            if text:
                filing_corpus.append(text)
                filing_keys.append(filing.receipt_no or str(filing.id))
        if filing_corpus:
            vectors = embed_texts(filing_corpus)
            for key, vec in zip(filing_keys, vectors):
                doc_vectors_filings[key] = vec

        news_corpus = []
        news_keys = []
        for news in recent_news:
            text = " ".join(part for part in [news.headline, news.summary, news.ticker] if part)
            if text:
                news_corpus.append(text)
                news_keys.append(str(news.id))
        if news_corpus:
            vectors = embed_texts(news_corpus)
            for key, vec in zip(news_keys, vectors):
                doc_vectors_news[key] = vec

        def _cosine(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        for (user_id,) in users:
            settings = read_user_proactive_settings(user_id)
            if not settings.settings.enabled:
                continue
            try:
                lm_settings = read_user_lightmem_settings(user_id).settings
                lightmem_enabled = bool(lm_settings.enabled)
            except Exception:
                lightmem_enabled = False
            tags = user_profile_service.list_interests(str(user_id))
            if not tags:
                continue
            tag_vectors = embed_texts(tags)
            if not tag_vectors:
                continue

            for filing in recent_filings:
                key = filing.receipt_no or str(filing.id)
                vec = doc_vectors_filings.get(key)
                if not vec:
                    continue
                score = max(_cosine(tag_vec, vec) for tag_vec in tag_vectors)
                if score < 0.8:
                    continue
                matched += 1
                summary_text = filing.summary if hasattr(filing, "summary") else None
                if lightmem_enabled:
                    hint = _maybe_memory_hint(
                        user_id,
                        " ".join(
                            part
                            for part in [
                                filing.ticker,
                                filing.corp_name,
                                filing.report_name,
                                filing.title,
                            ]
                            if part
                        ),
                    )
                    summary_text = _attach_memory_hint(summary_text, hint)
                res = proactive_service.upsert_notification(
                    db,
                    user_id=user_id,
                    source_type="filing",
                    source_id=filing.receipt_no or str(filing.id),
                    title=filing.report_name or filing.title,
                    summary=summary_text,
                    ticker=filing.ticker,
                    target_url=(filing.urls or {}).get("viewer") if hasattr(filing, "urls") else None,
                    metadata={
                        "corp_name": filing.corp_name,
                        "filed_at": filing.filed_at.isoformat() if filing.filed_at else None,
                        "similarity": score,
                        "embedding": _round_vec(vec),
                        "embedding_model": EMBEDDING_MODEL,
                    },
                )
                if res:
                    created += 1

            for news in recent_news:
                key = str(news.id)
                vec = doc_vectors_news.get(key)
                if not vec:
                    continue
                score = max(_cosine(tag_vec, vec) for tag_vec in tag_vectors)
                if score < 0.8:
                    continue
                matched += 1
                summary_text = news.summary
                if lightmem_enabled:
                    hint = _maybe_memory_hint(
                        user_id,
                        " ".join(part for part in [news.ticker, news.headline, news.summary] if part),
                    )
                    summary_text = _attach_memory_hint(summary_text, hint)
                res = proactive_service.upsert_notification(
                    db,
                    user_id=user_id,
                    source_type="news",
                    source_id=str(news.id),
                    title=news.headline,
                    summary=summary_text,
                    ticker=news.ticker,
                    target_url=news.url if hasattr(news, "url") else None,
                    metadata={
                        "publisher": getattr(news, "source", None),
                        "detected_at": news.detected_at.isoformat() if news.detected_at else None,
                        "similarity": score,
                        "embedding": _round_vec(vec),
                        "embedding_model": EMBEDDING_MODEL,
                    },
                )
                if res:
                    created += 1
        logger.info("proactive.scan completed: matched=%s created=%s window=%s", matched, created, window_minutes)
        return {"created": created, "matched": matched, "window_minutes": window_minutes}
    finally:
        db.close()
