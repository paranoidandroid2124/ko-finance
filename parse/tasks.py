"""Celery tasks orchestrating filings and Market Mood pipelines."""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from celery import shared_task
from pydantic import ValidationError
from sqlalchemy.orm import Session

import llm.llm_service as llm_service
from core.env import env_float, env_int
from database import SessionLocal
from ingest.dart_seed import seed_recent_filings as seed_recent_filings_job
from models.fact import ExtractedFact
from models.filing import Filing, STATUS_PENDING
from models.news import NewsObservation, NewsSignal
from models.summary import Summary
from parse.pdf_parser import extract_chunks
from parse.xml_parser import extract_chunks_from_xml
from schemas.news import NewsArticleCreate
from services import minio_service, vector_service
from services.notification_service import send_telegram_alert

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")


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
    valid_paths = [path for path in xml_paths if Path(path).is_file()]
    missing = set(xml_paths) - set(valid_paths)
    if missing:
        logger.warning("Missing XML files for filing %s: %s", filing.id, ", ".join(missing))
    return valid_paths


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
            vector_service.store_chunk_vectors(str(filing.id), chunks)
        else:
            logger.warning("No chunks extracted for filing %s", filing.id)

        raw_md = filing.raw_md or ""

        try:
            classification = llm_service.classify_filing_content(raw_md)
            filing.category = classification.get("category")
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
        db.commit()
        logger.info("Stored news signal %s for %s", news_signal.id, article.url)
        return str(news_signal.id)

    except Exception as exc:
        db.rollback()
        logger.error("Error processing news article %s: %s", getattr(article, "url", "unknown"), exc, exc_info=True)
        return "error"
    finally:
        db.close()


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
