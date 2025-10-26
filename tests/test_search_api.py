import importlib.util
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Text, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from models.company import CorpMetric
from models.filing import Filing
from models.news import NewsSignal, NewsWindowAggregate


def _load_search_router():
    spec = importlib.util.spec_from_file_location("search_router", Path("web/routers/search.py"))
    if spec.loader is None:
        raise RuntimeError("Unable to load search router module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def search_api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Filing.__table__.create(bind=engine)
    CorpMetric.__table__.create(bind=engine)

    topics_column = NewsSignal.__table__.c.get("topics")
    original_topics_type = None
    if topics_column is not None:
        original_topics_type = topics_column.type
        topics_column.type = Text()
    NewsSignal.__table__.create(bind=engine)
    if topics_column is not None:
        topics_column.type = original_topics_type

    NewsWindowAggregate.__table__.create(bind=engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    search_router = _load_search_router()
    app = FastAPI()
    app.include_router(search_router.router, prefix="/api/v1")

    def override_get_db():
        try:
            yield session
        finally:
            session.rollback()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    try:
        yield client, session
    finally:
        client.close()
        session.close()
        NewsWindowAggregate.__table__.drop(bind=engine)
        NewsSignal.__table__.drop(bind=engine)
        CorpMetric.__table__.drop(bind=engine)
        Filing.__table__.drop(bind=engine)
        engine.dispose()


def seed_sample_data(session):
    filing = Filing(
        id=uuid.uuid4(),
        corp_code="00123456",
        corp_name="Test Holdings",
        ticker="TEST",
        title="Test Filing Title",
        report_name="2024 Annual Report",
        category="Annual",
        filed_at=datetime(2025, 1, 3),
        created_at=datetime(2025, 1, 4),
        updated_at=datetime(2025, 1, 4, 12, 0),
    )
    article = NewsSignal(
        id=uuid.uuid4(),
        ticker="TEST",
        source="Test News",
        url="https://example.com/test-news",
        headline="Test News Headline",
        summary="Highlights for the filing",
        published_at=datetime(2025, 1, 5, 8, 30, tzinfo=timezone.utc),
        sentiment=0.4,
        source_reliability=0.82,
        created_at=datetime(2025, 1, 5, 8, 31, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 5, 9, 0, tzinfo=timezone.utc),
    )
    metric = CorpMetric(
        corp_code="00123456",
        corp_name="Test Holdings",
        ticker="TEST",
        metric_code="revenue",
        metric_name="Revenue",
        metric_group="financial",
        fiscal_year=2024,
        fiscal_period="FY",
        value=123.4,
        unit="KRW",
        source="test",
        observed_at=datetime(2025, 1, 4, tzinfo=timezone.utc),
    )
    aggregate = NewsWindowAggregate(
        id=uuid.uuid4(),
        scope="ticker",
        ticker="TEST",
        window_days=7,
        computed_for=datetime(2025, 1, 5, 9, 0, tzinfo=timezone.utc),
        article_count=12,
        avg_sentiment=0.25,
        sentiment_z=1.1,
        source_reliability=0.82,
    )
    session.add(filing)
    session.add(article)
    session.add(metric)
    session.add(aggregate)
    session.commit()
    return filing, article, metric, aggregate


def test_search_returns_filings_and_news(search_api_client):
    client, session = search_api_client
    filing, article, metric, aggregate = seed_sample_data(session)

    response = client.get("/api/v1/search?q=Test")
    assert response.status_code == 200

    payload = response.json()
    assert payload["query"] == "Test"
    assert payload["total"] >= 2
    assert payload["totals"]["filing"] == 1
    assert payload["totals"]["news"] == 1
    assert payload["totals"]["table"] == 1
    assert payload["totals"]["chart"] == 1

    items = {entry["type"]: entry for entry in payload["results"]}
    assert {"filing", "news", "table", "chart"}.issubset(items.keys())

    filing_result = items["filing"]
    assert filing_result["id"] == str(filing.id)
    assert filing_result["evidenceCounts"]["news"] == 1
    assert filing_result["sourceReliability"] == pytest.approx(0.82, rel=1e-3)
    assert filing_result["latestIngestedAt"]

    news_result = items["news"]
    assert news_result["id"] == str(article.id)
    assert news_result["evidenceCounts"]["filings"] == 1
    assert news_result["sourceReliability"] == pytest.approx(0.82, rel=1e-3)

    table_result = items["table"]
    assert table_result["evidenceCounts"]["tables"] == 1
    assert table_result["actions"]["exportLocked"] is False

    chart_result = items["chart"]
    assert chart_result["evidenceCounts"]["charts"] == 12
    assert chart_result["sourceReliability"] == pytest.approx(0.82, rel=1e-3)

    # 타입 필터가 적용되는지 확인
    filtered = client.get("/api/v1/search", params={"q": "Test", "types": "filing"})
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert all(entry["type"] == "filing" for entry in filtered_payload["results"])
    # totals 는 전체 집계를 유지
    assert filtered_payload["totals"]["filing"] == 1
    assert filtered_payload["totals"]["table"] == 1


def test_search_without_query_returns_recent(search_api_client):
    client, session = search_api_client
    seed_sample_data(session)

    response = client.get("/api/v1/search")
    assert response.status_code == 200

    payload = response.json()
    assert payload["query"] == ""
    assert payload["total"] >= 1
    assert any(entry["type"] == "filing" for entry in payload["results"])
