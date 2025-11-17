"""Business-layer helpers for dashboard overview aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.logging import get_logger
from models.filing import Filing
from models.news import NewsSignal
from schemas.api.dashboard import (
    DashboardAlert,
    DashboardEventItem,
    DashboardMetric,
    DashboardNewsItem,
    DashboardOverviewResponse,
    DashboardQuickLink,
    DashboardWatchlistSummary,
    FilingTrendPoint,
    FilingTrendResponse,
)
from services.watchlist_aggregator import (
    build_quick_link_payload,
    collect_watchlist_items,
    convert_items_to_alert_payload,
    summarise_watchlist_rules,
)

logger = get_logger(__name__)

DashboardTrend = str

EVENT_SEVERITY = {
    "capital_increase": "warning",
    "stock_buyback": "info",
    "large_contract": "info",
    "correction": "warning",
    "default": "info",
}

DEFAULT_QUICK_LINK = DashboardQuickLink(label="통합 검색 열기", href="/search", type="search")


@dataclass(frozen=True)
class DashboardRequestContext:
    """Caller-provided identifiers passed to dashboard aggregation."""

    user_id: Optional[UUID]
    org_id: Optional[UUID]


def build_dashboard_overview(
    db: Session,
    *,
    context: DashboardRequestContext,
) -> DashboardOverviewResponse:
    """Assemble the dashboard overview payload for the current session."""

    metrics = build_overview_metrics(db)
    watchlists, watchlist_alerts, quick_links = build_watchlist_summary(db, context=context)
    alerts = watchlist_alerts or build_overview_alerts(db)
    news_items = build_overview_news(db)
    events = build_today_events(db)

    return DashboardOverviewResponse(
        metrics=metrics,
        alerts=alerts,
        news=news_items,
        watchlists=watchlists,
        events=events,
        quickLinks=quick_links or [DEFAULT_QUICK_LINK],
    )


def build_overview_metrics(db: Session) -> List[DashboardMetric]:
    now_utc = datetime.now(timezone.utc)
    now_naive = now_utc.replace(tzinfo=None)
    current_start = now_naive - timedelta(hours=24)
    previous_start = now_naive - timedelta(hours=48)

    filings_current = (
        db.query(func.count(Filing.id))
        .filter(Filing.filed_at.isnot(None))
        .filter(Filing.filed_at >= current_start)
        .filter(Filing.filed_at <= now_naive)
        .scalar()
    ) or 0
    filings_previous = (
        db.query(func.count(Filing.id))
        .filter(Filing.filed_at.isnot(None))
        .filter(Filing.filed_at >= previous_start)
        .filter(Filing.filed_at < current_start)
        .scalar()
    ) or 0

    filings_metric = DashboardMetric(
        id="filings_24h",
        label="24시간 내 공시",
        value=filings_current,
        delta=format_delta_count(filings_current, filings_previous),
        trend=compute_trend(filings_current, filings_previous),
    )

    news_current = (
        db.query(func.count(NewsSignal.id))
        .filter(NewsSignal.detected_at >= current_start)
        .filter(NewsSignal.detected_at <= now_naive)
        .scalar()
    ) or 0
    news_previous = (
        db.query(func.count(NewsSignal.id))
        .filter(NewsSignal.detected_at >= previous_start)
        .filter(NewsSignal.detected_at < current_start)
        .scalar()
    ) or 0
    news_metric = DashboardMetric(
        id="news_24h",
        label="24시간 내 뉴스",
        value=news_current,
        delta=format_delta_count(news_current, news_previous),
        trend=compute_trend(news_current, news_previous),
    )

    filings_today = (
        db.query(func.count(Filing.id))
        .filter(Filing.filed_at >= now_naive.replace(hour=0, minute=0, second=0, microsecond=0))
        .filter(Filing.filed_at <= now_naive)
        .scalar()
    ) or 0
    filings_yesterday = (
        db.query(func.count(Filing.id))
        .filter(Filing.filed_at >= (now_naive - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
        .filter(Filing.filed_at < now_naive.replace(hour=0, minute=0, second=0, microsecond=0))
        .scalar()
    ) or 0
    filings_today_metric = DashboardMetric(
        id="filings_today",
        label="오늘 공시량",
        value=filings_today,
        delta=format_delta_pct(filings_today, filings_yesterday),
        trend=compute_trend(filings_today, filings_yesterday),
    )

    return [filings_metric, news_metric, filings_today_metric]


def build_overview_alerts(db: Session, limit: int = 10) -> List[DashboardAlert]:
    rows = (
        db.query(NewsSignal)
        .filter(NewsSignal.detected_at.isnot(None))
        .order_by(NewsSignal.detected_at.desc())
        .limit(limit)
        .all()
    )
    return [
        DashboardAlert(
            id=row.id,
            title=truncate_text(row.title or row.headline or "새로운 알림"),
            body=truncate_text(row.summary or row.snippet or row.body or ""),
            tone=map_sentiment(row.sentiment),
            timestamp=format_timespan(row.detected_at),
            targetUrl=row.article_url or row.source_url,
        )
        for row in rows
    ]


def build_overview_news(db: Session, limit: int = 6) -> List[DashboardNewsItem]:
    rows = (
        db.query(NewsSignal)
        .filter(NewsSignal.detected_at.isnot(None))
        .order_by(NewsSignal.detected_at.desc())
        .limit(limit)
        .all()
    )
    items: List[DashboardNewsItem] = []
    for row in rows:
        items.append(
            DashboardNewsItem(
                id=row.id,
                title=row.title or row.headline or "새로운 뉴스",
                summary=row.summary or row.snippet,
                ticker=row.ticker,
                corpName=row.corp_name,
                sentiment=map_sentiment(row.sentiment),
                timestamp=row.detected_at.isoformat() if row.detected_at else None,
                targetUrl=row.article_url or row.source_url,
            )
        )
    return items


def build_watchlist_summary(
    db: Session,
    *,
    context: DashboardRequestContext,
) -> Tuple[List[DashboardWatchlistSummary], List[DashboardAlert], List[DashboardQuickLink]]:
    items, summary_payload = collect_watchlist_items(
        db,
        user_id=context.user_id,
        org_id=context.org_id,
        limit=80,
    )
    if not items:
        return [], [], [DEFAULT_QUICK_LINK]

    summaries = summarise_watchlist_rules(items)[:3]
    watchlists = [
        DashboardWatchlistSummary(
            ruleId=summary.rule_id,
            name=summary.name,
            eventCount=summary.event_count,
            tickers=sorted(summary.tickers),
            channels=sorted(summary.channels),
            lastTriggeredAt=summary.last_triggered_at.isoformat() if summary.last_triggered_at else None,
            lastHeadline=summary.last_headline,
            detailUrl=f"/watchlist?ruleId={summary.rule_id}",
        )
        for summary in summaries
    ]

    alert_payloads = convert_items_to_alert_payload(items[:8])
    alerts = [
        DashboardAlert(
            id=payload["id"],
            title=payload["title"],
            body=payload["body"],
            timestamp=format_timespan(payload["timestamp"]),
            tone=map_sentiment(payload.get("sentiment")),
            targetUrl=payload.get("targetUrl") or (f"/company/{payload['ticker']}" if payload.get("ticker") else None),
        )
        for payload in alert_payloads
    ]

    quick_links_payload = build_quick_link_payload(summary_payload, items)
    quick_links = [
        DashboardQuickLink(label=entry["label"], href=entry["href"], type=entry["type"])
        for entry in quick_links_payload
    ]

    return watchlists, alerts, quick_links


def build_today_events(db: Session) -> List[DashboardEventItem]:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    filings = (
        db.query(Filing)
        .filter(Filing.filed_at.isnot(None))
        .filter(Filing.filed_at >= start_of_day)
        .order_by(Filing.filed_at.desc())
        .limit(12)
        .all()
    )

    events: List[DashboardEventItem] = []
    for filing in filings:
        category = (filing.category or "filing").lower()
        severity = EVENT_SEVERITY.get(category, EVENT_SEVERITY["default"])
        title = filing.report_name or filing.title or filing.category or "신규 공시"
        events.append(
            DashboardEventItem(
                id=str(filing.id),
                ticker=filing.ticker,
                corpName=filing.corp_name,
                title=title,
                eventType=category or "filing",
                filedAt=filing.filed_at.isoformat() if filing.filed_at else None,
                severity=severity if severity in {"info", "warning", "critical"} else "info",
                targetUrl=f"/filings?filingId={filing.id}",
            )
        )
    return events[:6]


def generate_filing_trend(db: Session, *, days: int = 7) -> FilingTrendResponse:
    if days < 1:
        days = 1
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    rows = (
        db.query(
            func.date(Filing.filed_at).label("filed_date"),
            func.count(Filing.id).label("count"),
        )
        .filter(Filing.filed_at >= datetime.combine(start_date, datetime.min.time()))
        .filter(Filing.filed_at <= datetime.combine(end_date, datetime.max.time()))
        .group_by(func.date(Filing.filed_at))
        .order_by(func.date(Filing.filed_at).asc())
        .all()
    )
    counts_by_date: Dict[date, int] = {
        row.filed_date: int(row.count) for row in rows if isinstance(row.filed_date, date)
    }

    points: List[FilingTrendPoint] = []
    rolling_window: List[int] = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        count = counts_by_date.get(day, 0)
        rolling_window.append(count)
        if len(rolling_window) > 3:
            rolling_window.pop(0)
        rolling_avg = sum(rolling_window) / len(rolling_window) if rolling_window else 0
        points.append(
            FilingTrendPoint(
                date=day.isoformat(),
                count=count,
                rolling_average=round(rolling_avg, 2),
            )
        )

    return FilingTrendResponse(points=points)


def compute_trend(current: float, previous: float | None) -> DashboardTrend:
    base = previous or 0.0
    change = current - base
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"


def format_delta_pct(current: float, previous: float | None) -> str:
    base = previous or 0.0
    if base == 0:
        if current == 0:
            return "0%"
        return f"+{current:.2f}"
    change = ((current - base) / base) * 100
    return f"{change:+.1f}%"


def format_delta_count(current: float, previous: float | None) -> str:
    base = previous or 0.0
    if base == 0:
        if current == 0:
            return "0건"
        return f"+{int(current)}건"
    change = ((current - base) / base) * 100
    return f"{change:+.1f}%"


def map_sentiment(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score <= -0.2:
        return "negative"
    if score >= 0.2:
        return "positive"
    return "neutral"


def format_timespan(timestamp: datetime | None) -> str:
    if timestamp is None:
        return "시간 정보 없음"
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - timestamp
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return "방금 전"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}분 전"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}시간 전"
    days = hours // 24
    return f"{days}일 전"


def truncate_text(value: str, limit: int = 60) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


__all__ = [
    "DashboardRequestContext",
    "build_dashboard_overview",
    "build_overview_alerts",
    "build_overview_metrics",
    "build_overview_news",
    "build_today_events",
    "build_watchlist_summary",
    "generate_filing_trend",
]
