import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.news import NewsSignal
from models.sector import NewsArticleSector, Sector, SectorDailyMetric
from services.aggregation.sector_classifier import ensure_sector_catalog
from services.aggregation.sector_metrics import (
    compute_sector_daily_metrics,
    compute_sector_window_metrics,
    list_top_articles_for_sector,
)


def _add_daily_history(session: Session, sector: Sector, *, days: int, end_day: date) -> None:
    for offset in range(1, days + 1):
        day = end_day - timedelta(days=offset)
        session.add(
            SectorDailyMetric(
                sector_id=sector.id,
                date=day,
                sent_mean=0.0,
                sent_std=0.0,
                volume=2,
            )
        )
    session.flush()


def test_sector_metrics_pipeline_generates_daily_and_window_rows(db_session: Session):
    sectors = ensure_sector_catalog(db_session)
    semiconductor = sectors['semiconductor']

    as_of_day = date(2025, 1, 15)
    _add_daily_history(db_session, semiconductor, days=14, end_day=as_of_day)

    published_at = datetime(2025, 1, 14, 23, 30, tzinfo=timezone.utc)
    signal = NewsSignal(
        id=uuid.uuid4(),
        ticker=None,
        source='TestSource',
        url='https://example.com/article',
        headline='Test Article',
        summary='Test Summary',
        published_at=published_at,
        sentiment=0.8,
        topics=['semi'],
        evidence=None,
    )
    db_session.add(signal)
    db_session.flush()
    db_session.add(NewsArticleSector(article_id=signal.id, sector_id=semiconductor.id, weight=1.0))
    db_session.commit()

    daily = compute_sector_daily_metrics(db_session, as_of_day, as_of_day)
    db_session.commit()

    assert daily, 'daily metrics should be generated'
    metric = daily[0]
    assert metric.sector_id == semiconductor.id
    assert metric.date == as_of_day
    assert metric.volume == 1
    assert metric.sent_mean is not None

    records = compute_sector_window_metrics(db_session, as_of_day, window_days=(7, 30))
    db_session.commit()

    assert records, 'window metrics should be generated'
    seven_day = next((item for item in records if item.window_days == 7), None)
    assert seven_day is not None
    assert seven_day.top_article_id == signal.id
    assert seven_day.vol_sum >= 1
    assert seven_day.delta_sent_7d is not None

    top_articles = list_top_articles_for_sector(
        db_session,
        semiconductor.id,
        datetime(2025, 1, 15, 12, tzinfo=timezone.utc),
    )
    assert top_articles
    article, score = top_articles[0]
    assert article.id == signal.id
    assert score > 0
