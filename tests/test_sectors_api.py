import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from models.news import NewsSignal
from models.sector import NewsArticleSector, Sector, SectorDailyMetric
from services.aggregation.sector_classifier import ensure_sector_catalog
from services.aggregation.sector_metrics import compute_sector_daily_metrics, compute_sector_window_metrics
import web.routers.sectors as sectors_router


@pytest.fixture()
def sector_api_client():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    sectors = ensure_sector_catalog(session)
    semiconductor = sectors['semiconductor']

    as_of_day = date(2025, 1, 15)
    # Seed historical daily metrics for baseline
    for offset in range(1, 15):
        day = as_of_day - timedelta(days=offset)
        session.add(
            SectorDailyMetric(
                sector_id=semiconductor.id,
                date=day,
                sent_mean=0.05 * offset,
                sent_std=0.0,
                volume=2,
            )
        )

    published_at = datetime(2025, 1, 14, 23, 30, tzinfo=timezone.utc)
    signal = NewsSignal(
        id=uuid.uuid4(),
        ticker=None,
        source='TestSource',
        url='https://example.com/signal',
        headline='Test Article',
        summary='Test Summary',
        published_at=published_at,
        sentiment=0.9,
        topics=['semi'],
        evidence=None,
    )
    session.add(signal)
    session.flush()
    session.add(NewsArticleSector(article_id=signal.id, sector_id=semiconductor.id, weight=1.0))
    session.commit()

    # Compute daily + window metrics for use in API responses
    compute_sector_daily_metrics(session, as_of_day, as_of_day)
    compute_sector_window_metrics(session, as_of_day, window_days=(7, 30))
    session.commit()

    app = FastAPI()
    app.include_router(sectors_router.router, prefix='/api/v1')

    def override_get_db():
        try:
            yield session
        finally:
            session.rollback()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    try:
        yield client, session, semiconductor, signal
    finally:
        client.close()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_sector_signals_endpoint_returns_points(sector_api_client):
    client, _, sector, _ = sector_api_client
    response = client.get('/api/v1/sectors/signals?window=7')
    assert response.status_code == 200
    payload = response.json()
    assert payload['windowDays'] == 7
    assert payload['points']
    point = payload['points'][0]
    assert point['sector']['id'] == sector.id
    assert 'sentimentZ' in point
    assert 'topArticle' in point


def test_sector_timeseries_endpoint_exposes_series(sector_api_client):
    client, _, sector, _ = sector_api_client
    response = client.get(f'/api/v1/sectors/{sector.id}/timeseries?days=14')
    assert response.status_code == 200
    payload = response.json()
    assert payload['sector']['id'] == sector.id
    assert len(payload['series']) >= 1
    assert 'current' in payload


def test_sector_top_articles_endpoint_lists_recent(sector_api_client):
    client, _, sector, signal = sector_api_client
    response = client.get(f'/api/v1/sectors/{sector.id}/top-articles?hours=72&limit=3')
    assert response.status_code == 200
    payload = response.json()
    assert payload['sector']['id'] == sector.id
    assert payload['items']
    assert payload['items'][0]['id'] == str(signal.id)
