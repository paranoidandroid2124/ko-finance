"\"\"\"FastAPI router exposing sector-level sentiment analytics.\"\"\""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from database import get_db
from models.news import NewsSignal
from models.sector import Sector, SectorDailyMetric, SectorWindowMetric
from schemas.api.sectors import (
    SectorCurrentSnapshot,
    SectorRef,
    SectorSignalPoint,
    SectorSignalsResponse,
    SectorTimeseriesPoint,
    SectorTimeseriesResponse,
    SectorTopArticle,
    SectorTopArticlesResponse,
)
from services.aggregation.sector_metrics import list_top_articles_for_sector

router = APIRouter(prefix="/sectors", tags=["Sectors"])

KST = ZoneInfo("Asia/Seoul")


def _to_sector_ref(sector: Sector) -> SectorRef:
    return SectorRef(id=sector.id, slug=sector.slug, name=sector.name)


@router.get("/signals", response_model=SectorSignalsResponse)
def list_sector_signals(
    window: int = Query(7, ge=1, le=180),
    asof: Optional[date] = None,
    db: Session = Depends(get_db),
) -> SectorSignalsResponse:
    """Return scatterplot-friendly sector signals for a given window."""
    stmt = db.query(func.max(SectorWindowMetric.asof_date)).filter(SectorWindowMetric.window_days == window)
    latest_date = stmt.scalar()
    as_of_date = asof or latest_date
    if as_of_date is None:
        return SectorSignalsResponse(asOf=date.today(), windowDays=window, points=[])

    records = (
        db.query(SectorWindowMetric, Sector, NewsSignal)
        .join(Sector, Sector.id == SectorWindowMetric.sector_id)
        .outerjoin(NewsSignal, NewsSignal.id == SectorWindowMetric.top_article_id)
        .filter(SectorWindowMetric.window_days == window)
        .filter(SectorWindowMetric.asof_date == as_of_date)
        .all()
    )

    points: List[SectorSignalPoint] = []
    for window_metric, sector, article in records:
        top_article = None
        if article:
            top_article = SectorTopArticle(
                id=article.id,
                title=article.headline,
                summary=article.summary,
                url=article.url,
                targetUrl=article.url,
                tone=article.sentiment,
                publishedAt=article.published_at,
            )

        point = SectorSignalPoint(
            sector=_to_sector_ref(sector),
            sentimentZ=window_metric.sent_z or 0.0,
            volumeZ=window_metric.vol_z or 0.0,
            deltaSentiment7d=window_metric.delta_sent_7d,
            sentimentMean=window_metric.sent_mean,
            volumeSum=window_metric.vol_sum,
            topArticle=top_article,
        )
        points.append(point)

    return SectorSignalsResponse(asOf=as_of_date, windowDays=window, points=points)


@router.get("/{sector_id}/timeseries", response_model=SectorTimeseriesResponse)
def get_sector_timeseries(
    sector_id: int,
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
) -> SectorTimeseriesResponse:
    """Return sparkline-ready timeseries for a sector."""
    sector = db.query(Sector).filter(Sector.id == sector_id).one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    latest_day = (
        db.query(func.max(SectorDailyMetric.date))
        .filter(SectorDailyMetric.sector_id == sector_id)
        .scalar()
    )
    if latest_day is None:
        latest_day = date.today()

    start_day = latest_day - timedelta(days=days - 1)

    rows = (
        db.query(SectorDailyMetric)
        .filter(SectorDailyMetric.sector_id == sector_id)
        .filter(SectorDailyMetric.date >= start_day)
        .filter(SectorDailyMetric.date <= latest_day)
        .order_by(SectorDailyMetric.date.asc())
        .all()
    )
    series = [
        SectorTimeseriesPoint(date=row.date, sentMean=row.sent_mean, volume=row.volume or 0)
        for row in rows
    ]

    current_window = (
        db.query(SectorWindowMetric)
        .filter(SectorWindowMetric.sector_id == sector_id)
        .filter(SectorWindowMetric.window_days == 7)
        .order_by(SectorWindowMetric.asof_date.desc())
        .first()
    )
    snapshot = SectorCurrentSnapshot(
        sentZ7d=current_window.sent_z if current_window else None,
        delta7d=current_window.delta_sent_7d if current_window else None,
    )

    return SectorTimeseriesResponse(
        sector=_to_sector_ref(sector),
        series=series,
        current=snapshot,
    )


@router.get("/{sector_id}/top-articles", response_model=SectorTopArticlesResponse)
def get_sector_top_articles(
    sector_id: int,
    hours: int = Query(72, ge=1, le=168),
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
) -> SectorTopArticlesResponse:
    """Return top articles for a sector using recency/tone weighting."""
    sector = db.query(Sector).filter(Sector.id == sector_id).one_or_none()
    if sector is None:
        raise HTTPException(status_code=404, detail="Sector not found")

    now_local = datetime.now(KST)
    articles = list_top_articles_for_sector(
        db,
        sector_id=sector_id,
        as_of=now_local,
        hours=hours,
        limit=limit,
    )

    items = [
        SectorTopArticle(
            id=signal.id,
            title=signal.headline,
            summary=signal.summary,
            url=signal.url,
            targetUrl=signal.url,
            tone=signal.sentiment,
            publishedAt=signal.published_at,
        )
        for signal, _ in articles
    ]

    return SectorTopArticlesResponse(sector=_to_sector_ref(sector), items=items)
