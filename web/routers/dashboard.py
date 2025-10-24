from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.filing import Filing
from models.news import NewsSignal
from schemas.api.dashboard import (
    DashboardAlert,
    DashboardMetric,
    DashboardNewsItem,
    DashboardOverviewResponse,
    FilingTrendPoint,
    FilingTrendResponse,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DashboardTrend = str


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


def build_metrics(db: Session) -> list[DashboardMetric]:
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

    filings_trend = compute_trend(float(filings_current), float(filings_previous))
    filings_delta = format_delta_count(float(filings_current), float(filings_previous))

    sentiment_window_hours = 6
    sentiment_start = now_utc - timedelta(hours=sentiment_window_hours)
    sentiment_previous_start = now_utc - timedelta(hours=sentiment_window_hours * 2)

    sentiment_current = (
        db.query(func.avg(NewsSignal.sentiment))
        .filter(NewsSignal.published_at >= sentiment_start)
        .filter(NewsSignal.published_at <= now_utc)
        .scalar()
    )
    sentiment_previous = (
        db.query(func.avg(NewsSignal.sentiment))
        .filter(NewsSignal.published_at >= sentiment_previous_start)
        .filter(NewsSignal.published_at < sentiment_start)
        .scalar()
    )

    sentiment_value = float(sentiment_current or 0.0)
    sentiment_trend = compute_trend(sentiment_value, float(sentiment_previous or 0.0))
    sentiment_delta = format_delta_pct(sentiment_value, float(sentiment_previous or 0.0))

    articles_current = (
        db.query(func.count(NewsSignal.id))
        .filter(NewsSignal.published_at >= sentiment_start)
        .filter(NewsSignal.published_at <= now_utc)
        .scalar()
    ) or 0
    articles_previous = (
        db.query(func.count(NewsSignal.id))
        .filter(NewsSignal.published_at >= sentiment_previous_start)
        .filter(NewsSignal.published_at < sentiment_start)
        .scalar()
    ) or 0

    articles_trend = compute_trend(float(articles_current), float(articles_previous))
    articles_delta = format_delta_count(float(articles_current), float(articles_previous))

    metrics = [
        DashboardMetric(
            title="최근 24시간 공시",
            value=f"{filings_current}건",
            delta=filings_delta,
            trend=filings_trend,
            description="최근 24시간 동안 접수된 공시 수",
        ),
        DashboardMetric(
            title="평균 뉴스 감성",
            value=f"{sentiment_value:.2f}",
            delta=sentiment_delta,
            trend=sentiment_trend,
            description=f"최근 {sentiment_window_hours}시간 뉴스 평균 감성 점수",
        ),
        DashboardMetric(
            title="뉴스 기사 수",
            value=f"{articles_current}건",
            delta=articles_delta,
            trend=articles_trend,
            description=f"최근 {sentiment_window_hours}시간 수집된 기사 수",
        ),
    ]

    return metrics


def build_alerts(db: Session) -> list[DashboardAlert]:
    now_utc = datetime.now(timezone.utc)
    recent_filings = (
        db.query(Filing)
        .filter(Filing.filed_at.isnot(None))
        .order_by(Filing.filed_at.desc())
        .limit(5)
        .all()
    )
    recent_news = (
        db.query(NewsSignal)
        .filter(NewsSignal.published_at <= now_utc)
        .order_by(NewsSignal.published_at.desc())
        .limit(5)
        .all()
    )

    events: list[tuple[datetime, DashboardAlert]] = []

    for filing in recent_filings:
        base_time = filing.filed_at or filing.created_at
        alert = DashboardAlert(
            id=str(filing.id),
            title="신규 공시",
            body=f"{filing.corp_name or filing.ticker or '기업'} {filing.report_name or filing.title or '공시'}",
            timestamp=format_timespan(base_time),
            tone="neutral",
            targetUrl=f"/filings?filingId={filing.id}",
        )
        if base_time is None:
            base_time = datetime.now()
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)
        events.append((base_time, alert))

    for signal in recent_news:
        base_time = signal.published_at or now_utc
        tone = map_sentiment(signal.sentiment)
        body = (
            f"{signal.source} · 감성 {signal.sentiment:.2f}"
            if signal.sentiment is not None
            else signal.source
        )
        alert = DashboardAlert(
            id=str(signal.id),
            title="뉴스 업데이트",
            body=body,
            timestamp=format_timespan(signal.published_at),
            tone=tone,
            targetUrl=signal.url,
        )
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)
        events.append((base_time, alert))

    events.sort(key=lambda item: item[0], reverse=True)
    return [alert for _, alert in events[:5]]


def build_news_items(db: Session) -> list[DashboardNewsItem]:
    now_utc = datetime.now(timezone.utc)
    recent_news = (
        db.query(NewsSignal)
        .filter(NewsSignal.published_at <= now_utc)
        .order_by(NewsSignal.published_at.desc())
        .limit(8)
        .all()
    )

    items: list[DashboardNewsItem] = []
    for news in recent_news:
        sentiment_label = map_sentiment(news.sentiment)
        items.append(
            DashboardNewsItem(
                id=str(news.id),
                title=news.headline,
                sentiment=sentiment_label,
                source=news.source,
                publishedAt=format_timespan(news.published_at),
                url=news.url,
            )
        )
    return items


def generate_filing_trend(
    db: Session,
    *,
    days: int = 7,
) -> FilingTrendResponse:
    if days < 1:
        days = 1
    if days > 30:
        days = 30

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    start_datetime = datetime.combine(start_date, datetime.min.time())

    # Fetch filing counts grouped by day
    grouped = (
        db.query(func.date_trunc("day", Filing.filed_at).label("filed_day"), func.count(Filing.id))
        .filter(Filing.filed_at.isnot(None))
        .filter(Filing.filed_at >= start_datetime)
        .group_by("filed_day")
        .order_by("filed_day")
        .all()
    )

    counts_by_day: dict[date, int] = {}
    for filed_day, count in grouped:
        if filed_day is None:
            continue
        key = filed_day.date() if hasattr(filed_day, "date") else filed_day
        counts_by_day[key] = int(count or 0)

    points: list[FilingTrendPoint] = []
    rolling_window: list[int] = []

    for index in range(days):
        day = start_date + timedelta(days=index)
        count = counts_by_day.get(day, 0)
        rolling_window.append(count)
        if len(rolling_window) > 7:
            rolling_window.pop(0)
        rolling_avg = sum(rolling_window) / len(rolling_window) if rolling_window else 0.0
        points.append(
            FilingTrendPoint(
                date=day.isoformat(),
                count=count,
                rolling_average=round(rolling_avg, 2),
            )
        )

    return FilingTrendResponse(points=points)


@router.get("/overview", response_model=DashboardOverviewResponse)
def read_dashboard_overview(db: Session = Depends(get_db)) -> DashboardOverviewResponse:
    metrics = build_metrics(db)
    alerts = build_alerts(db)
    news_items = build_news_items(db)
    return DashboardOverviewResponse(metrics=metrics, alerts=alerts, news=news_items)


@router.get("/filing-trend", response_model=FilingTrendResponse)
def read_filing_trend(days: int = 7, db: Session = Depends(get_db)) -> FilingTrendResponse:
    return generate_filing_trend(db, days=days)
