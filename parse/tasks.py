"""Celery tasks orchestrating filings and Market Mood pipelines."""

from __future__ import annotations

import logging
import os
import uuid
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from celery import shared_task
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import llm.llm_service as llm_service
from core.env import env_float, env_int, env_str
from database import SessionLocal
from ingest.dart_seed import seed_recent_filings as seed_recent_filings_job
from ingest.news_fetcher import fetch_news_batch
from models.chat import ChatMessage, ChatSession
from models.fact import ExtractedFact
from models.filing import Filing, STATUS_PENDING
from models.digest import DailyDigestLog
from models.news import NewsObservation, NewsSignal
from models.summary import Summary
from parse.pdf_parser import extract_chunks
from parse.xml_parser import extract_chunks_from_xml
from schemas.news import NewsArticleCreate
from services import chat_service, minio_service, vector_service
from services.aggregation.sector_classifier import assign_article_to_sector
from services.aggregation.sector_metrics import compute_sector_daily_metrics, compute_sector_window_metrics
from services.aggregation.news_metrics import compute_news_window_metrics
from services.notification_service import send_telegram_alert

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

DIGEST_ZONE = ZoneInfo("Asia/Seoul")
SECTOR_ZONE = ZoneInfo("Asia/Seoul")
DIGEST_TOP_LIMIT = env_int("DAILY_DIGEST_TOP_N", 3, minimum=1)
DIGEST_BASE_URL = env_str("FILINGS_DASHBOARD_URL", "https://kofilot.com/filings")
DIGEST_CHANNEL = "telegram"
SUMMARY_RECENT_TURNS = env_int("CHAT_MEMORY_RECENT_TURNS", 3, minimum=1)
SUMMARY_TRIGGER_MESSAGES = env_int("CHAT_SUMMARY_TRIGGER_MESSAGES", 20, minimum=6)
NEWS_FETCH_LIMIT = env_int("NEWS_FETCH_LIMIT", 5, minimum=1)

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
    meta: Dict[str, Any] = {
        "ticker": filing.ticker,
        "corp_code": filing.corp_code,
        "corp_name": filing.corp_name,
        "market": filing.market,
        "report_name": filing.report_name,
        "category": filing.category,
    }
    filed_at = filing.filed_at
    if filed_at:
        if filed_at.tzinfo is None:
            filed_at = filed_at.replace(tzinfo=timezone.utc)
        meta["filed_at_iso"] = filed_at.isoformat()
        meta["filed_at_ts"] = filed_at.timestamp()
    return {key: value for key, value in meta.items() if value not in (None, "")}


def _open_session() -> Session:
    return SessionLocal()


def _ensure_pdf_path(filing: Filing) -> Optional[str]:
    if filing.file_path and Path(filing.file_path).is_file():
        return filing.file_path

    source_files = filing.source_files or {}
    pdf_path = source_files.get("pdf") if isinstance(source_files, dict) else None
    if pdf_path and Path(pdf_path).is_file():
        filing.file_path = pdf_path
        return pdf_path

    urls = filing.urls or {}
    object_name = urls.get("minio_object") or urls.get("minio_url")
    if object_name and minio_service.is_enabled():
        local_path = Path(UPLOAD_DIR) / f"{filing.receipt_no or filing.id}.pdf"
        downloaded = minio_service.download_file(object_name, str(local_path))
        if downloaded:
            filing.file_path = downloaded
            return downloaded

    logger.warning("PDF file not available for filing %s", filing.id)
    return None


def _load_xml_paths(filing: Filing) -> List[str]:
    source_files = filing.source_files or {}
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
            object_name = entry.get("object") or entry.get("minio_object")
            remote_url = entry.get("url")
        else:
            continue

        if candidate_path and Path(candidate_path).is_file():
            resolved_paths.append(candidate_path)
            continue

        if object_name and minio_service.is_enabled():
            target_path = cache_dir / Path(object_name).name
            downloaded = minio_service.download_file(object_name, str(target_path))
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


def _save_chunks(filing: Filing, chunks: List[Dict[str, Any]], db: Session) -> None:
    filing.chunks = chunks
    filing.raw_md = "\n\n".join(
        chunk["content"] for chunk in chunks if isinstance(chunk.get("content"), str)
    )
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
    record.who = summary.get("who")
    record.what = summary.get("what")
    record.when = summary.get("when")
    record.where = summary.get("where")
    record.how = summary.get("how")
    record.why = summary.get("why")
    record.insight = summary.get("insight")
    record.confidence_score = summary.get("confidence_score")
    db.commit()


def _format_notification(filing: Filing, summary: Dict[str, Any]) -> str:
    parts = ["*[DART Watcher+]*"]
    title = filing.report_name or filing.title or "Untitled filing"
    if filing.ticker:
        parts.append(f"*{filing.ticker}* {title}")
    else:
        parts.append(title)
    insight = summary.get("insight") or summary.get("what") or "Summary is not available."
    parts.append(f"- Summary: {insight}")
    viewer_url = (filing.urls or {}).get("viewer")
    if viewer_url:
        parts.append(f"[View original document]({viewer_url})")
    parts.append("_(For information only. This is not investment advice.)_")
    return "\n".join(parts)


@shared_task(name="system.health_check")
def health_check() -> str:
    return "ok"


@shared_task(name="m1.seed_recent_filings")
def seed_recent_filings_task(days_back: int = 1) -> int:
    logger.info("Running DART seeding task for the last %d day(s).", days_back)
    return seed_recent_filings_job(days_back=days_back)


@shared_task(name="m1.process_filing")
def process_filing(filing_id: str) -> str:
    db = _open_session()
    try:
        filing = db.query(Filing).filter(Filing.id == filing_id).one_or_none()
        if not filing:
            logger.error("Filing %s not found.", filing_id)
            return "missing"

        pdf_path = _ensure_pdf_path(filing)
        xml_paths = _load_xml_paths(filing)

        chunks: List[Dict[str, Any]] = []
        if pdf_path:
            chunks.extend(extract_chunks(pdf_path))
        if xml_paths:
            chunks.extend(extract_chunks_from_xml(xml_paths))

        if chunks:
            _save_chunks(filing, chunks, db)
            vector_metadata = _build_vector_metadata(filing)
            vector_service.store_chunk_vectors(str(filing.id), chunks, metadata=vector_metadata)
        else:
            logger.warning("No chunks extracted for filing %s", filing.id)

        raw_md = filing.raw_md or ""

        try:
            classification = llm_service.classify_filing_content(raw_md)
            normalized_category = _normalize_category_label(classification.get("category"))
            filing.category = normalized_category
            filing.category_confidence = classification.get("confidence_score")
            db.commit()
        except Exception as exc:
            logger.error("Classification failed for %s: %s", filing.id, exc, exc_info=True)

        facts_payload: List[Dict[str, Any]] = []
        try:
            extraction = llm_service.extract_structured_info(raw_md)
            facts_payload = _normalize_facts(extraction.get("facts"))
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", filing.id, exc, exc_info=True)

        if facts_payload:
            try:
                checked = llm_service.self_check_extracted_info(raw_md, facts_payload)
                corrected = checked.get("corrected_json", {}).get("facts") or checked.get("corrected_json")
                normalized = _normalize_facts(corrected) if corrected else facts_payload
                _save_facts(filing, normalized, db)
            except Exception as exc:
                logger.error("Self-check failed for %s: %s", filing.id, exc, exc_info=True)
                _save_facts(filing, facts_payload, db)

        try:
            summary = llm_service.summarize_filing_content(raw_md)
            _save_summary(filing, summary, db)
            message = _format_notification(filing, summary)
            send_telegram_alert(message)
        except Exception as exc:
            logger.error("Summary/notification failed for %s: %s", filing.id, exc, exc_info=True)

        filing.status = "COMPLETED"
        filing.analysis_status = "ANALYZED"
        db.commit()
        return "completed"

    except Exception as exc:
        logger.error("Error processing filing %s: %s", filing_id, exc, exc_info=True)
        return "error"
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
    article_count = 0
    positive_count = 0
    neutral_count = 0
    negative_count = 0
    sentiments: List[float] = []
    topic_counter: Counter[str] = Counter()

    for signal in signals:
        article_count += 1
        sentiment = signal.sentiment
        if sentiment is None:
            neutral_count += 1
        else:
            sentiments.append(sentiment)
            if sentiment > neutral_threshold:
                positive_count += 1
            elif sentiment < -neutral_threshold:
                negative_count += 1
            else:
                neutral_count += 1

        for topic in signal.topics or []:
            topic_counter[topic] += 1

    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None
    min_sentiment = min(sentiments) if sentiments else None
    max_sentiment = max(sentiments) if sentiments else None

    top_topics = [
        {"topic": topic, "count": count}
        for topic, count in topic_counter.most_common(topics_limit)
    ]

    return {
        "window_start": window_start,
        "window_end": window_end,
        "article_count": article_count,
        "positive_count": positive_count,
        "neutral_count": neutral_count,
        "negative_count": negative_count,
        "avg_sentiment": avg_sentiment,
        "min_sentiment": min_sentiment,
        "max_sentiment": max_sentiment,
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
        validated = llm_service.validate_news_analysis_result(analysis)

        sentiment = validated.get("sentiment")
        topics = validated.get("topics") or []
        rationale = validated.get("rationale")
        evidence = {"rationale": rationale} if rationale else None

        news_signal = NewsSignal(
            ticker=article.ticker,
            source=article.source,
            url=article.url,
            headline=article.headline,
            summary=article.summary,
            published_at=article.published_at,
            sentiment=sentiment,
            topics=topics,
            evidence=evidence,
        )
        db.add(news_signal)
        try:
            assign_article_to_sector(db, news_signal)
        except Exception as exc:
            logger.warning("Failed to assign sector for news signal %s: %s", article.url, exc, exc_info=True)
        db.commit()
        logger.info("Stored news signal %s for %s", news_signal.id, article.url)
        return str(news_signal.id)

    except Exception as exc:
        db.rollback()
        logger.error("Error processing news article %s: %s", getattr(article, "url", "unknown"), exc, exc_info=True)
        return "error"
    finally:
        db.close()


@shared_task(name="m2.seed_news_feeds")
def seed_news_feeds(limit_per_feed: Optional[int] = None, use_mock_fallback: bool = False) -> int:
    """Fetch latest news articles and enqueue them for processing."""
    fetch_limit = max(1, int(limit_per_feed or NEWS_FETCH_LIMIT))
    queued = 0

    try:
        articles = fetch_news_batch(limit_per_feed=fetch_limit, use_mock_fallback=use_mock_fallback)
    except Exception as exc:
        logger.error("Failed to fetch news batch: %s", exc, exc_info=True)
        return queued

    if not articles:
        logger.info("No news articles fetched from feeds.")
        return queued

    for article in articles:
        try:
            payload = article.model_dump() if hasattr(article, "model_dump") else dict(article)
            process_news_article.delay(payload)
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

        tickers = {signal.ticker for signal in signals if getattr(signal, "ticker", None)}

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


def _get_digest_bounds(target: date) -> Tuple[datetime, datetime]:
    """Return UTC window (naive) covering the given local date."""
    start_local = datetime.combine(target, time.min, tzinfo=DIGEST_ZONE)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def _load_digest_filings(
    db: Session,
    bounds: Tuple[datetime, datetime],
    limit: int,
) -> Tuple[int, List[Filing]]:
    """Fetch count and top filings for the digest window."""
    start_utc, end_utc = bounds
    total = (
        db.query(Filing)
        .filter(Filing.created_at >= start_utc, Filing.created_at < end_utc)
        .count()
    )
    if total == 0:
        return 0, []

    top_filings = (
        db.query(Filing)
        .filter(Filing.created_at >= start_utc, Filing.created_at < end_utc)
        .order_by(Filing.created_at.desc())
        .limit(limit)
        .all()
    )
    return total, top_filings


def _check_digest_sent(db: Session, digest_date: date) -> bool:
    """Return True if the digest was already sent for the given date."""
    record = (
        db.query(DailyDigestLog)
        .filter(
            DailyDigestLog.digest_date == digest_date,
            DailyDigestLog.channel == DIGEST_CHANNEL,
        )
        .first()
    )
    return record is not None


def _mark_digest_sent(db: Session, digest_date: date) -> None:
    """Persist that the digest was delivered."""
    entry = DailyDigestLog(digest_date=digest_date, channel=DIGEST_CHANNEL)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("Digest already recorded for %s", digest_date.isoformat())


def _build_digest_message(digest_date: date, total: int, filings: List[Filing]) -> str:
    """Compose the Telegram digest message."""
    date_str = digest_date.isoformat()
    lines = [
        f"[일일 공시 요약] {date_str}",
        "오늘자 공시가 업데이트되었습니다.",
        f"오늘 등록된 공시: {total}건",
    ]

    for filing in filings:
        corp = filing.corp_name or filing.ticker or "알수없음"
        title = filing.report_name or filing.title or "공시"
        lines.append(f"- {corp}: {title}")

    remaining = total - len(filings)
    if remaining > 0:
        lines.append(f"...외 {remaining}건")

    if DIGEST_BASE_URL:
        connector = "&" if "?" in DIGEST_BASE_URL else "?"
        lines.append(f"자세히 보기: {DIGEST_BASE_URL}{connector}date={date_str}")

    return "\n".join(lines)


@shared_task(name="m4.send_filing_digest")
def send_filing_digest(target_date_iso: Optional[str] = None) -> str:
    """Send a weekday filing digest to Telegram."""
    reference = datetime.now(DIGEST_ZONE)
    if target_date_iso:
        try:
            parsed = datetime.fromisoformat(target_date_iso)
            if parsed.tzinfo is None:
                reference = parsed.replace(tzinfo=DIGEST_ZONE)
            else:
                reference = parsed.astimezone(DIGEST_ZONE)
        except ValueError:
            logger.warning("Invalid target_date_iso '%s'. Using current time.", target_date_iso)

    digest_date = reference.date()
    if digest_date.weekday() >= 5:
        logger.info("Skipping filing digest on weekend: %s", digest_date.isoformat())
        return "skipped_weekend"

    bounds = _get_digest_bounds(digest_date)
    db = _open_session()
    try:
        if _check_digest_sent(db, digest_date):
            logger.info("Digest already sent for %s", digest_date.isoformat())
            return "skipped_duplicate"

        total, filings = _load_digest_filings(db, bounds, DIGEST_TOP_LIMIT)
        message = _build_digest_message(digest_date, total, filings)

        if not send_telegram_alert(message):
            logger.error("Telegram digest send failed for %s", digest_date.isoformat())
            return "send_failed"

        _mark_digest_sent(db, digest_date)
        logger.info("Daily filing digest sent for %s (total=%d)", digest_date.isoformat(), total)
        return "sent"
    except Exception as exc:
        db.rollback()
        logger.error("Daily digest failed for %s: %s", digest_date.isoformat(), exc, exc_info=True)
        return "error"
    finally:
        db.close()


def _flatten_citation_entries(meta: Dict[str, Any]) -> List[str]:
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
        if not message.content:
            continue
        payload.append({"role": message.role, "content": message.content})
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

        snapshot = session.memory_snapshot or {}
        summarized_until = int(snapshot.get("summarized_until") or 0)

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_uuid)
            .order_by(ChatMessage.seq.asc())
            .all()
        )
        if not messages:
            return "no_messages"

        unsummarized = [message for message in messages if message.seq > summarized_until]
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
            citations.extend(_flatten_citation_entries(message.meta))
        unique_citations = sorted({item for item in citations if item})

        snapshot_payload = dict(snapshot)
        snapshot_payload["summary"] = summary_text
        snapshot_payload["citations"] = unique_citations
        snapshot_payload["summarized_until"] = archive_candidates[-1].seq
        snapshot_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        session.memory_snapshot = snapshot_payload
        if summary_text:
            session.summary = chat_service.trim_preview(summary_text)

        max_seq = archive_candidates[-1].seq
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
