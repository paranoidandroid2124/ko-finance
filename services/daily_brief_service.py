"""Assemble daily brief payloads from recent filings, news, and RAG telemetry."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
import uuid

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.env import env_float, env_int
from core.logging import get_logger
try:
    from database import SessionLocal  # type: ignore
except RuntimeError as exc:  # DATABASE_URL may be missing during tests
    SessionLocal = None  # type: ignore[assignment]
    _SESSION_IMPORT_ERROR = exc
else:
    _SESSION_IMPORT_ERROR = None
from models.alert import AlertDelivery, AlertRule
from models.evidence import EvidenceSnapshot
from models.filing import Filing
from models.news import NewsSignal
from services import admin_rag_service, storage_service
from services.id_utils import normalize_uuid
from services.aggregation.news_statistics import build_top_topics, summarize_news_signals
from services.daily_brief_renderer import render_daily_brief
from services.watchlist_utils import is_watchlist_rule

import llm.llm_service as llm_service

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DAILY_BRIEF_OUTPUT_ROOT = REPO_ROOT / "build" / "daily_brief"
MANIFEST_FILENAME = "manifest.json"

KST = ZoneInfo("Asia/Seoul")
DEFAULT_REPORT_TITLE = "AI Market Signals"
DAILY_BRIEF_CHANNEL = "daily_brief_pdf"
MAX_EVIDENCE_ITEMS = env_int("DAILY_BRIEF_EVIDENCE_LIMIT", 5, minimum=1)
TOP_TOPIC_LIMIT = env_int("DAILY_BRIEF_TOP_TOPIC_LIMIT", 5, minimum=1)
NEWS_NEUTRAL_THRESHOLD = env_float("NEWS_NEUTRAL_THRESHOLD", 0.15, minimum=0.0)
NEWS_MIN_RELIABILITY = env_float("DAILY_BRIEF_NEWS_MIN_RELIABILITY", 0.45, minimum=0.0)
NEWS_TOP_TICKER_LIMIT = env_int("DAILY_BRIEF_TOP_TICKER_LIMIT", 5, minimum=1)
NEWS_TOP_SOURCE_LIMIT = env_int("DAILY_BRIEF_TOP_SOURCE_LIMIT", 5, minimum=1)
ALERT_TOP_TICKER_LIMIT = env_int("DAILY_BRIEF_ALERT_TOP_TICKER_LIMIT", 5, minimum=1)
ALERT_TOP_CATEGORY_LIMIT = env_int("DAILY_BRIEF_ALERT_TOP_CATEGORY_LIMIT", 5, minimum=1)
def _ensure_session(session: Optional[Session]) -> Tuple[Session, bool]:
    if session is not None:
        return session, False
    if SessionLocal is None:
        raise RuntimeError("SessionLocal is unavailable; DATABASE_URL must be configured.") from _SESSION_IMPORT_ERROR
    db = SessionLocal()
    return db, True


def _daily_bounds(target_date: date, *, tz: ZoneInfo = KST) -> Tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _format_delta(current: int, previous: int) -> str:
    delta = current - previous
    if delta > 0:
        return f"+{delta} vs D-1"
    if delta < 0:
        return f"{delta} vs D-1"
    return "= vs D-1"


def _count_filings(session: Session, *, start: datetime, end: datetime) -> Dict[str, Any]:
    filed_filter = or_(
        and_(Filing.filed_at.isnot(None), Filing.filed_at >= start, Filing.filed_at < end),
        and_(Filing.filed_at.is_(None), Filing.created_at >= start, Filing.created_at < end),
    )
    total = session.query(func.count(Filing.id)).filter(filed_filter).scalar() or 0
    unique_companies = (
        session.query(func.count(func.distinct(Filing.corp_name)))
        .filter(filed_filter, Filing.corp_name.isnot(None))
        .scalar()
        or 0
    )
    company_rows = (
        session.query(Filing.corp_name, func.count(Filing.id).label("cnt"))
        .filter(filed_filter, Filing.corp_name.isnot(None))
        .group_by(Filing.corp_name)
        .order_by(func.count(Filing.id).desc())
        .limit(5)
        .all()
    )
    top_companies = [row[0] for row in company_rows if row[0]]
    return {
        "count": int(total),
        "unique_companies": int(unique_companies),
        "top_companies": top_companies,
    }


def _summarize_news(session: Session, *, start: datetime, end: datetime) -> Dict[str, Any]:
    rows: List[NewsSignal] = (
        session.query(NewsSignal)
        .filter(NewsSignal.published_at >= start, NewsSignal.published_at < end)
        .order_by(NewsSignal.published_at.asc())
        .all()
    )

    if not rows:
        return {
            "count": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "avg_sentiment": 0.0,
            "top_topics": [],
            "top_topics_detail": [],
            "top_tickers": [],
            "top_positive_tickers": [],
            "top_sources": [],
            "filtered_count": 0,
            "raw_count": 0,
        }

    reliable_rows: List[NewsSignal] = []
    for row in rows:
        reliability = getattr(row, "source_reliability", None)
        if reliability is None or reliability >= NEWS_MIN_RELIABILITY:
            reliable_rows.append(row)

    analysis_rows = reliable_rows or rows

    summary = summarize_news_signals(analysis_rows, neutral_threshold=NEWS_NEUTRAL_THRESHOLD)
    top_topics_detail = build_top_topics(summary.topic_counts, TOP_TOPIC_LIMIT, include_weights=True)
    dominant_topics = [entry["topic"] for entry in top_topics_detail]
    avg_sentiment = summary.avg_sentiment if summary.avg_sentiment is not None else 0.0

    ticker_counter: Counter[str] = Counter()
    positive_ticker_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()

    for signal in analysis_rows:
        ticker = (getattr(signal, "ticker", None) or "").strip()
        if ticker:
            ticker_counter[ticker] += 1
            sentiment = getattr(signal, "sentiment", None)
            if sentiment is not None and sentiment > NEWS_NEUTRAL_THRESHOLD:
                positive_ticker_counter[ticker] += 1
        source = (getattr(signal, "source", None) or "").strip()
        if source:
            source_counter[source] += 1

    return {
        "count": summary.article_count,
        "positive": summary.positive_count,
        "neutral": summary.neutral_count,
        "negative": summary.negative_count,
        "avg_sentiment": avg_sentiment,
        "top_topics": dominant_topics,
        "top_topics_detail": top_topics_detail,
        "top_tickers": [ticker for ticker, _ in ticker_counter.most_common(NEWS_TOP_TICKER_LIMIT)],
        "top_positive_tickers": [
            ticker for ticker, _ in positive_ticker_counter.most_common(NEWS_TOP_TICKER_LIMIT)
        ],
        "top_sources": [source for source, _ in source_counter.most_common(NEWS_TOP_SOURCE_LIMIT)],
        "filtered_count": len(analysis_rows),
        "raw_count": len(rows),
    }


def _count_news(session: Session, *, start: datetime, end: datetime) -> int:
    return (
        session.query(func.count(NewsSignal.id))
        .filter(NewsSignal.published_at >= start, NewsSignal.published_at < end)
        .scalar()
        or 0
    )


def _summarize_alerts(session: Session, *, start: datetime, end: datetime) -> Dict[str, Any]:
    rows = (
        session.query(AlertDelivery, AlertRule)
        .join(AlertRule, AlertRule.id == AlertDelivery.alert_id)
        .filter(AlertDelivery.created_at >= start, AlertDelivery.created_at < end)
        .all()
    )

    if not rows:
        return {
            "count": 0,
            "top_channels": [],
            "channel_counts": {},
            "status": {},
            "event_types": {},
            "top_tickers": [],
            "watchlist": {"count": 0, "tickers": [], "rules": []},
            "news": {"count": 0, "sources": [], "tickers": []},
            "filing": {"count": 0, "categories": []},
        }

    channel_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    event_type_counter: Counter[str] = Counter()
    ticker_counter: Counter[str] = Counter()
    news_ticker_counter: Counter[str] = Counter()
    news_source_counter: Counter[str] = Counter()
    filing_category_counter: Counter[str] = Counter()
    watchlist_ticker_counter: Counter[str] = Counter()
    watchlist_rule_counter: Counter[str] = Counter()

    watchlist_delivery_count = 0
    news_delivery_count = 0
    filing_delivery_count = 0

    for delivery, rule in rows:
        channel = (delivery.channel or "unknown").lower()
        status = (delivery.status or "unknown").lower()
        channel_counter[channel] += 1
        status_counter[status] += 1

        trigger_payload = rule.trigger if isinstance(rule.trigger, dict) else {}
        event_type = str(trigger_payload.get("type") or "filing").lower()
        event_type_counter[event_type] += 1
        if event_type == "news":
            news_delivery_count += 1
        elif event_type == "filing":
            filing_delivery_count += 1

        context = delivery.context if isinstance(delivery.context, dict) else {}
        raw_events = context.get("events") if isinstance(context.get("events"), list) else []
        events: List[Mapping[str, Any]] = [event for event in raw_events if isinstance(event, Mapping)]

        category_match = any("watch" in str(event.get("category") or "").lower() for event in events)
        watchlist_rule = is_watchlist_rule(rule)
        is_watchlist = watchlist_rule or category_match
        if is_watchlist:
            watchlist_delivery_count += 1
            rule_label = (rule.name or str(rule.id))[:80]
            watchlist_rule_counter[rule_label] += 1

        for event in events:
            ticker = str(event.get("ticker") or "").strip()
            if ticker:
                ticker_counter[ticker] += 1
                if is_watchlist:
                    watchlist_ticker_counter[ticker] += 1
                if event_type == "news":
                    news_ticker_counter[ticker] += 1
            if event_type == "news":
                source = str(event.get("source") or "").strip()
                if source:
                    news_source_counter[source] += 1
            if event_type == "filing":
                category = str(event.get("category") or "").strip()
                if category:
                    filing_category_counter[category] += 1

    return {
        "count": len(rows),
        "top_channels": [channel for channel, _ in channel_counter.most_common(3)],
        "channel_counts": dict(channel_counter),
        "status": dict(status_counter),
        "event_types": dict(event_type_counter),
        "top_tickers": [ticker for ticker, _ in ticker_counter.most_common(ALERT_TOP_TICKER_LIMIT)],
        "watchlist": {
            "count": watchlist_delivery_count,
            "tickers": [ticker for ticker, _ in watchlist_ticker_counter.most_common(ALERT_TOP_TICKER_LIMIT)],
            "rules": [rule for rule, _ in watchlist_rule_counter.most_common(ALERT_TOP_TICKER_LIMIT)],
        },
        "news": {
            "count": news_delivery_count,
            "sources": [source for source, _ in news_source_counter.most_common(NEWS_TOP_SOURCE_LIMIT)],
            "tickers": [ticker for ticker, _ in news_ticker_counter.most_common(ALERT_TOP_TICKER_LIMIT)],
        },
        "filing": {
            "count": filing_delivery_count,
            "categories": [
                category for category, _ in filing_category_counter.most_common(ALERT_TOP_CATEGORY_LIMIT)
            ],
        },
    }


def _collect_evidence(
    session: Session,
    *,
    start: datetime,
    end: datetime,
    limit: int,
    fallback_date: date,
    fallback_headline: str,
) -> List[Dict[str, Any]]:
    snapshots: List[EvidenceSnapshot] = (
        session.query(EvidenceSnapshot)
        .filter(EvidenceSnapshot.updated_at >= start, EvidenceSnapshot.updated_at < end)
        .order_by(EvidenceSnapshot.updated_at.desc())
        .limit(limit)
        .all()
    )
    evidence: List[Dict[str, Any]] = []
    for snapshot in snapshots:
        payload = snapshot.payload or {}
        source = payload.get("source") or payload.get("source_name") or payload.get("channel") or "Evidence"
        title = payload.get("title") or payload.get("headline") or payload.get("summary") or "요약 근거"
        body = (
            payload.get("body")
            or payload.get("summary")
            or payload.get("quote")
            or payload.get("content")
            or ""
        )
        recorded = snapshot.updated_at.astimezone(KST).date().isoformat() if snapshot.updated_at else fallback_date.isoformat()
        evidence.append(
            {
                "source": str(source),
                "date": recorded,
                "title": str(title),
                "body": str(body),
                "trace_id": str(payload.get("trace_id") or payload.get("traceId") or ""),
                "url": str(payload.get("url") or payload.get("source_url") or payload.get("link") or ""),
            }
        )

    if evidence:
        return evidence

    # Fallback entry to satisfy renderer requirements.
    return [
        {
            "source": "System",
            "date": fallback_date.isoformat(),
            "title": "수집된 근거가 충분하지 않습니다",
            "body": fallback_headline or "브리핑에 필요한 근거가 아직 수집되지 않았습니다.",
            "trace_id": "",
            "url": "",
        }
    ]


def _build_signals(
    *,
    filings_today: Dict[str, Any],
    filings_prev: Dict[str, Any],
    news_today_count: int,
    news_prev_count: int,
    news_summary: Dict[str, Any],
    alerts_today: Dict[str, Any],
    alerts_prev: Dict[str, Any],
) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []

    signals.append(
        {
            "label": "OpenDART filings (24h)",
            "value": str(filings_today["count"]),
            "delta": _format_delta(filings_today["count"], filings_prev["count"]),
            "note": "상위 기업: "
            + ", ".join(filings_today["top_companies"][:3])
            if filings_today["top_companies"]
            else "주요 기업 변동 없음",
            "severity": "primary",
        }
    )

    news_note_parts: List[str] = []
    top_topics = news_summary.get("top_topics") or []
    if top_topics:
        news_note_parts.append("토픽: " + ", ".join(top_topics[:3]))
    positive_tickers = news_summary.get("top_positive_tickers") or []
    if positive_tickers:
        news_note_parts.append("강세 종목: " + ", ".join(positive_tickers[:3]))
    avg_sentiment = news_summary.get("avg_sentiment")
    if avg_sentiment is not None and news_summary.get("count"):
        news_note_parts.append(f"평균 감성 {avg_sentiment:.2f}")
    if not news_note_parts:
        news_note_parts.append("토픽 변동 없음")
    signals.append(
        {
            "label": "News meta (24h)",
            "value": str(news_today_count),
            "delta": _format_delta(news_today_count, news_prev_count),
            "note": " · ".join(news_note_parts),
            "severity": "info",
        }
    )

    watchlist_today = alerts_today.get("watchlist") or {}
    watchlist_prev = alerts_prev.get("watchlist") or {}
    watchlist_count = int(watchlist_today.get("count") or 0)
    watchlist_delta = _format_delta(watchlist_count, int(watchlist_prev.get("count") or 0))

    alert_note_parts: List[str] = []
    top_channels = alerts_today.get("top_channels") or []
    if top_channels:
        alert_note_parts.append("TOP 채널: " + ", ".join(top_channels[:2]))
    if watchlist_count:
        alert_note_parts.append(f"워치리스트 {watchlist_count}건")
    news_alerts = alerts_today.get("news") or {}
    if news_alerts.get("count"):
        alert_note_parts.append(f"뉴스 알림 {news_alerts['count']}건")
    if not alert_note_parts:
        alert_note_parts.append("전달 채널 고르게 분포")
    signals.append(
        {
            "label": "Alert deliveries",
            "value": str(alerts_today["count"]),
            "delta": _format_delta(alerts_today["count"], alerts_prev["count"]),
            "note": " · ".join(alert_note_parts),
            "severity": "warn" if alerts_today["count"] > alerts_prev["count"] else "accent",
        }
    )

    if watchlist_count:
        top_watchlist = watchlist_today.get("tickers") or []
        watch_note = (
            "상위 종목: " + ", ".join(top_watchlist[:3]) if top_watchlist else "상위 워치리스트 경보 확인 필요"
        )
        signals.append(
            {
                "label": "Watchlist alerts",
                "value": str(watchlist_count),
                "delta": watchlist_delta,
                "note": watch_note,
                "severity": "warn" if watchlist_count > int(watchlist_prev.get("count") or 0) else "accent",
            }
        )

    return signals


def _build_alerts(
    news_summary: Dict[str, Any],
    filings_today: Dict[str, Any],
    alerts_today: Dict[str, Any],
) -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []
    if news_summary.get("top_topics"):
        alerts.append(
            {
                "title": "뉴스 토픽 주목",
                "body": f"주요 토픽 {', '.join(news_summary['top_topics'][:3])} 가 부각되었습니다.",
                "severity": "warn",
            }
        )

    watchlist_today = alerts_today.get("watchlist") or {}
    watchlist_count = int(watchlist_today.get("count") or 0)
    if watchlist_count:
        top_watchlist = watchlist_today.get("tickers") or []
        body = f"워치리스트 경보 {watchlist_count}건 발생"
        if top_watchlist:
            body += f": {', '.join(top_watchlist[:3])}"
        alerts.append(
            {
                "title": "워치리스트 경보",
                "body": body,
                "severity": "warn",
            }
        )

    filing_categories = alerts_today.get("filing", {}).get("categories") or []
    if filing_categories:
        alerts.append(
            {
                "title": "공시 카테고리 집중",
                "body": "주요 카테고리: " + ", ".join(filing_categories[:3]),
                "severity": "info",
            }
        )
    elif filings_today["top_companies"]:
        alerts.append(
            {
                "title": "공시 집중 기업",
                "body": f"공시가 몰린 기업: {', '.join(filings_today['top_companies'][:3])}",
                "severity": "info",
            }
        )

    return alerts


def _build_actions(alerts_today: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    if alerts_today["count"] > 0:
        actions.append(
            {
                "title": "알림 후속 조치",
                "ordered": True,
                "items": [
                    "상위 채널별 전달 성공률을 점검하세요.",
                    "완료되지 않은 고위험 알림에 대한 재점검을 예약하세요.",
                ],
            }
        )
    actions.append(
        {
            "title": "데이터 품질 점검",
            "ordered": False,
            "items": [
                "뉴스 토픽 상위 3건을 확인하고 RAG 근거에 반영하세요.",
                "공시 집중 기업에 대한 워치리스트 트리거를 검토하세요.",
            ],
        }
    )
    return actions


def _build_metrics(rag_summary: Dict[str, Any]) -> List[Dict[str, str]]:
    metrics: List[Dict[str, str]] = []
    target_minutes = (rag_summary.get("slaTargetMs") or 0) / 60000 if rag_summary.get("slaTargetMs") else None
    p50 = rag_summary.get("p50DurationMs")
    p95 = rag_summary.get("p95DurationMs")
    if p50 is not None:
        metrics.append(
            {
                "label": "재색인 p50",
                "current": f"{p50 / 60000:.1f} min",
                "delta": f"SLA {target_minutes:.0f}m" if target_minutes else "=",
            }
        )
    if p95 is not None:
        metrics.append(
            {
                "label": "재색인 p95",
                "current": f"{p95 / 60000:.1f} min",
                "delta": f"SLA {target_minutes:.0f}m" if target_minutes else "=",
            }
        )
    metrics.append(
        {
            "label": "재색인 실행",
            "current": str(rag_summary.get("totalRuns", 0)),
            "delta": f"성공 {rag_summary.get('completed', 0)} · 실패 {rag_summary.get('failed', 0)}",
        }
    )
    metrics.append(
        {
            "label": "SLA 위반",
            "current": str(rag_summary.get("slaBreaches", 0)),
            "delta": f"준수 {rag_summary.get('slaMet', 0)}",
        }
    )
    return metrics


def _build_appendix(filings_today: Dict[str, Any], news_summary: Dict[str, Any]) -> Dict[str, Any]:
    sections: List[Dict[str, Any]] = []
    if filings_today["top_companies"]:
        sections.append(
            {
                "title": "공시 집중 기업",
                "type": "list",
                "items": filings_today["top_companies"],
            }
        )
    if news_summary["top_topics"]:
        sections.append(
            {
                "title": "뉴스 토픽",
                "type": "list",
                "items": news_summary["top_topics"],
            }
        )
    return {"sections": sections} if sections else {}


def _build_notes(
    filings_today: Dict[str, Any],
    news_summary: Dict[str, Any],
    alerts_today: Dict[str, Any],
    trend_summary: Optional[str],
) -> List[str]:
    notes: List[str] = []
    if trend_summary:
        notes.append(trend_summary)
    notes.append(f"공시 수집 기업 수: {filings_today['unique_companies']}")
    notes.append(
        f"뉴스 감성 분포 — 긍정 {news_summary['positive']}, 중립 {news_summary['neutral']}, 부정 {news_summary['negative']}"
    )
    filtered_count = news_summary.get("filtered_count")
    raw_count = news_summary.get("raw_count")
    if raw_count and filtered_count is not None and filtered_count < raw_count:
        notes.append(f"신뢰도 {NEWS_MIN_RELIABILITY:.2f}+ 뉴스 {filtered_count}/{raw_count}건 반영")
    top_sources = news_summary.get("top_sources") or []
    if top_sources:
        notes.append("주요 뉴스 소스: " + ", ".join(top_sources[:3]))
    watchlist_today = alerts_today.get("watchlist") or {}
    watchlist_count = int(watchlist_today.get("count") or 0)
    if watchlist_count:
        top_watchlist = watchlist_today.get("tickers") or []
        watch_note = f"워치리스트 경보 {watchlist_count}건"
        if top_watchlist:
            watch_note += f" — {', '.join(top_watchlist[:3])}"
        notes.append(watch_note)
    if alerts_today.get("top_channels"):
        notes.append("알림 전달 채널 Top: " + ", ".join(alerts_today["top_channels"][:3]))
    else:
        notes.append("알림 채널 분포 균형 유지")
    return notes


def _load_previous_alerts(session: Session, *, start: datetime, end: datetime) -> Dict[str, Any]:
    return _summarize_alerts(session, start=start, end=end)


def build_daily_brief_payload(
    *,
    reference_date: Optional[date] = None,
    session: Optional[Session] = None,
    use_llm: bool = True,
    top_n_overrides: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Collect daily metrics and compose the LaTeX renderer payload."""

    ref_date = reference_date or datetime.now(KST).date()
    today_start, today_end = _daily_bounds(ref_date)
    prev_start, prev_end = _daily_bounds(ref_date - timedelta(days=1))

    db, owns_session = _ensure_session(session)
    try:
        filings_today = _count_filings(db, start=today_start, end=today_end)
        filings_prev = _count_filings(db, start=prev_start, end=prev_end)

        news_today_count = _count_news(db, start=today_start, end=today_end)
        news_prev_count = _count_news(db, start=prev_start, end=prev_end)
        news_summary = _summarize_news(db, start=today_start, end=today_end)

        alerts_today = _summarize_alerts(db, start=today_start, end=today_end)
        alerts_prev = _load_previous_alerts(db, start=prev_start, end=prev_end)

        rag_history = admin_rag_service.list_reindex_history(limit=80)
        rag_summary = admin_rag_service.summarize_reindex_history(rag_history)

        evidence = _collect_evidence(
            db,
            start=today_start,
            end=today_end,
            limit=MAX_EVIDENCE_ITEMS,
            fallback_date=ref_date,
            fallback_headline="일일 브리프",
        )

        trend_summary_text: Optional[str] = None
        headline_text = f"{ref_date.isoformat()} 일일 브리프"
        if use_llm:
            trend_context = {
                "date": ref_date.isoformat(),
                "filings": {
                    "count": filings_today["count"],
                    "delta": filings_today["count"] - filings_prev["count"],
                    "top_companies": filings_today["top_companies"],
                },
                "news": {
                    "count": news_today_count,
                    "delta": news_today_count - news_prev_count,
                    "avg_sentiment": news_summary.get("avg_sentiment"),
                    "top_topics": news_summary.get("top_topics"),
                },
                "alerts": {
                    "count": alerts_today["count"],
                    "delta": alerts_today["count"] - alerts_prev["count"],
                    "top_channels": alerts_today["top_channels"],
                },
            }
            try:
                trend_result = llm_service.generate_daily_brief_trend(trend_context)
                if isinstance(trend_result, Mapping):
                    headline_text = str(trend_result.get("headline") or headline_text)
                    summary_value = trend_result.get("summary") or trend_result.get("overview")
                    if summary_value:
                        trend_summary_text = str(summary_value)
            except Exception as exc:  # pragma: no cover - LLM failure should not break pipeline
                logger.warning("Daily brief trend generation failed: %s", exc, exc_info=True)

        signals = _build_signals(
            filings_today=filings_today,
            filings_prev=filings_prev,
            news_today_count=news_today_count,
            news_prev_count=news_prev_count,
            news_summary=news_summary,
            alerts_today=alerts_today,
            alerts_prev=alerts_prev,
        )
        alerts = _build_alerts(news_summary, filings_today, alerts_today)
        actions = _build_actions(alerts_today)
        metrics = _build_metrics(rag_summary)
        appendix = _build_appendix(filings_today, news_summary)
        notes = _build_notes(filings_today, news_summary, alerts_today, trend_summary_text)

        top_n = {
            "signals": 6,
            "alerts": 3,
            "actions": 2,
            "evidence": 4,
            "metrics": 5,
            "notes": 4,
        }
        if top_n_overrides:
            top_n.update({key: int(value) for key, value in top_n_overrides.items() if isinstance(value, int)})

        latest_trace_urls = rag_summary.get("latestTraceUrls") or []
        links = {}
        if latest_trace_urls:
            links["trace_url"] = latest_trace_urls[0]

        payload = {
            "report": {
                "title": DEFAULT_REPORT_TITLE,
                "date": ref_date.isoformat(),
                "headline": headline_text,
                "top_n": top_n,
            },
            "signals": signals,
            "alerts": alerts,
            "actions": actions,
            "evidence": evidence,
            "metrics": metrics,
            "notes": notes,
            "appendix": appendix,
            "links": links,
            "charts": {},
        }
        return payload
    finally:
        if owns_session:
            db.close()


def render_daily_brief_document(
    *,
    payload: Optional[Dict[str, Any]] = None,
    reference_date: Optional[date] = None,
    output_dir: Path,
    tex_name: str = "daily_brief.tex",
    compile_pdf: bool = False,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Build the payload if needed and render through the LaTeX helper."""

    if payload is None:
        payload = build_daily_brief_payload(reference_date=reference_date, session=session)

    result_paths = render_daily_brief(payload, output_dir, tex_name=tex_name, compile_pdf_output=compile_pdf)

    effective_date = reference_date
    if effective_date is None:
        report_date = payload.get("report", {}).get("date") if isinstance(payload.get("report"), Mapping) else None
        if isinstance(report_date, str):
            try:
                effective_date = date.fromisoformat(report_date)
            except ValueError:
                effective_date = None

    storage_manifest: Optional[Dict[str, Any]] = None
    if effective_date is not None:
        storage_manifest = _store_daily_brief_artifacts(effective_date, output_dir, result_paths)

    return {"payload": payload, "outputs": result_paths, "storage": storage_manifest}


def resolve_daily_brief_paths(reference_date: date, *, tex_name: Optional[str] = None) -> Dict[str, Path]:
    """Return canonical filesystem paths for a daily brief render."""

    folder = DAILY_BRIEF_OUTPUT_ROOT / reference_date.isoformat()
    resolved_tex = tex_name or f"daily_brief_{reference_date.isoformat()}.tex"
    tex_path = folder / resolved_tex
    pdf_path = tex_path.with_suffix(".pdf")
    manifest_path = folder / MANIFEST_FILENAME
    return {"folder": folder, "tex": tex_path, "pdf": pdf_path, "manifest": manifest_path}


def _relative_to_repo(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _write_manifest(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem guard
        logger.warning("Failed to write daily brief manifest: %s", exc, exc_info=True)


def _read_manifest(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - manifest corruption guard
        logger.warning("Failed to read daily brief manifest %s: %s", path, exc, exc_info=True)
        return {}


def _upload_artifact(reference_date: date, artifact_path: Path, *, content_type: str) -> Optional[str]:
    if not storage_service.is_enabled() or not artifact_path.is_file():
        return None
    object_name = f"daily-brief/{reference_date.isoformat()}/{artifact_path.name}"
    return storage_service.upload_file(str(artifact_path), object_name=object_name, content_type=content_type)


def _store_daily_brief_artifacts(
    reference_date: date,
    output_dir: Path,
    outputs: Mapping[str, Path],
) -> Dict[str, Any]:
    manifest_path = output_dir / MANIFEST_FILENAME
    artifacts: Dict[str, Any] = {}
    for key, content_type in (("tex", "application/x-tex"), ("pdf", "application/pdf")):
        path = outputs.get(key)
        if not path:
            continue
        path = Path(path)
        entry: Dict[str, Any] = {
            "local_path": _relative_to_repo(path),
            "local_exists": path.is_file(),
            "provider": storage_service.provider_name(),
        }
        if entry["local_exists"]:
            uploaded_key = _upload_artifact(reference_date, path, content_type=content_type)
            if uploaded_key:
                entry["object_name"] = uploaded_key
                entry["uploaded_at"] = datetime.now(timezone.utc).isoformat()
        artifacts[key] = entry

    manifest = _read_manifest(manifest_path)
    manifest.update(
        {
            "reference_date": reference_date.isoformat(),
            "channel": DAILY_BRIEF_CHANNEL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts,
        }
    )
    _write_manifest(manifest_path, manifest)
    return manifest


def _resolve_remote_url(entry: Mapping[str, Any]) -> Optional[str]:
    object_name = entry.get("object_name")
    if not object_name or not storage_service.is_enabled():
        return None
    return storage_service.get_presigned_url(object_name)


def list_daily_brief_runs(
    *,
    limit: int = 10,
    session: Optional[Session] = None,  # retained for backward compatibility
) -> List[Dict[str, Any]]:
    """List recent daily brief generations using filesystem manifests."""

    _ = session  # unused
    limit = max(int(limit or 10), 1)
    if not DAILY_BRIEF_OUTPUT_ROOT.exists():
        return []

    entries: List[Tuple[date, Path]] = []
    for child in DAILY_BRIEF_OUTPUT_ROOT.iterdir():
        if not child.is_dir():
            continue
        try:
            folder_date = date.fromisoformat(child.name)
        except ValueError:
            continue
        entries.append((folder_date, child))

    entries.sort(key=lambda item: item[0], reverse=True)
    runs: List[Dict[str, Any]] = []
    for folder_date, _ in entries[:limit]:
        paths = resolve_daily_brief_paths(folder_date)
        tex_path = paths["tex"]
        pdf_path = paths["pdf"]
        manifest = _read_manifest(paths["manifest"])
        artifacts = manifest.get("artifacts", {}) if isinstance(manifest, Mapping) else {}
        tex_manifest = artifacts.get("tex", {}) if isinstance(artifacts, Mapping) else {}
        pdf_manifest = artifacts.get("pdf", {}) if isinstance(artifacts, Mapping) else {}

        tex_exists = tex_path.exists()
        pdf_exists = pdf_path.exists()
        tex_size = tex_path.stat().st_size if tex_exists else None
        pdf_size = pdf_path.stat().st_size if pdf_exists else None

        runs.append(
            {
                "id": manifest.get("id") or f"{folder_date.isoformat()}-{manifest.get('channel', DAILY_BRIEF_CHANNEL)}",
                "reference_date": folder_date,
                "channel": manifest.get("channel", DAILY_BRIEF_CHANNEL),
                "generated_at": manifest.get("generated_at"),
                "tex": {
                    "path": tex_manifest.get("local_path") or _relative_to_repo(tex_path),
                    "exists": tex_exists,
                    "size_bytes": tex_size,
                    "provider": tex_manifest.get("provider"),
                    "download_url": _resolve_remote_url(tex_manifest),
                },
                "pdf": {
                    "path": pdf_manifest.get("local_path") or _relative_to_repo(pdf_path),
                    "exists": pdf_exists,
                    "size_bytes": pdf_size,
                    "provider": pdf_manifest.get("provider"),
                    "download_url": _resolve_remote_url(pdf_manifest),
                },
            }
        )

    return runs


def has_brief_been_generated(
    session: Optional[Session],
    *,
    reference_date: date,
    channel: str = DAILY_BRIEF_CHANNEL,
) -> bool:
    """Returns True if a brief artifact exists for the date."""

    _ = session  # unused
    paths = resolve_daily_brief_paths(reference_date)
    pdf_exists = paths["pdf"].exists()
    tex_exists = paths["tex"].exists()
    return pdf_exists or tex_exists


def record_brief_generation(
    session: Optional[Session],
    *,
    reference_date: date,
    channel: str = DAILY_BRIEF_CHANNEL,
) -> None:
    """Persist metadata for the generated brief without touching the database."""

    _ = session  # unused
    paths = resolve_daily_brief_paths(reference_date)
    manifest_path = paths["manifest"]
    manifest = _read_manifest(manifest_path)
    manifest.update(
        {
            "reference_date": reference_date.isoformat(),
            "channel": channel,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _write_manifest(manifest_path, manifest)



def cleanup_daily_brief_artifacts(
    *,
    retention_days: int = 30,
    session: Optional[Session] = None,
) -> Dict[str, int]:
    """Delete stale daily brief files (local + remote) older than the retention window."""

    retention_days = max(int(retention_days or 1), 1)
    cutoff = datetime.now(KST).date() - timedelta(days=retention_days)

    summary = {
        "folders_deleted": 0,
        "objects_deleted": 0,
        "manifests_updated": 0,
        "folders_skipped": 0,
    }

    if not DAILY_BRIEF_OUTPUT_ROOT.exists():
        return summary

    for entry in DAILY_BRIEF_OUTPUT_ROOT.iterdir():
        if not entry.is_dir():
            continue
        try:
            folder_date = date.fromisoformat(entry.name)
        except ValueError:
            logger.debug("Skipping non-date folder under daily brief output: %s", entry)
            continue
        if folder_date > cutoff:
            summary["folders_skipped"] += 1
            continue

        manifest_path = entry / MANIFEST_FILENAME
        manifest_data = _read_manifest(manifest_path)
        artifacts = manifest_data.get("artifacts", {}) if isinstance(manifest_data, Mapping) else {}
        updated_manifest = False

        for key, artifact_entry in list(artifacts.items()):
            if not isinstance(artifact_entry, Mapping):
                continue
            object_name = artifact_entry.get("object_name")
            if object_name and storage_service.is_enabled():
                if storage_service.delete_object(object_name):
                    summary["objects_deleted"] += 1
                    artifact_entry = dict(artifact_entry)
                    artifact_entry["object_deleted_at"] = datetime.now(timezone.utc).isoformat()
                    artifact_entry.pop("object_name", None)
                    artifacts[key] = artifact_entry
                    updated_manifest = True

        if updated_manifest:
            manifest_data["artifacts"] = artifacts
            _write_manifest(manifest_path, manifest_data)
            summary["manifests_updated"] += 1

        try:
            shutil.rmtree(entry, ignore_errors=False)
            summary["folders_deleted"] += 1
        except OSError as exc:  # pragma: no cover - filesystem guard
            logger.warning("Failed to remove daily brief folder %s: %s", entry, exc, exc_info=True)

    return summary


__all__ = [
    "DAILY_BRIEF_CHANNEL",
    "DAILY_BRIEF_OUTPUT_ROOT",
    "build_daily_brief_payload",
    "has_brief_been_generated",
    "record_brief_generation",
    "list_daily_brief_runs",
    "resolve_daily_brief_paths",
    "render_daily_brief_document",
    "cleanup_daily_brief_artifacts",
]
