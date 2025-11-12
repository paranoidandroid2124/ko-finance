import uuid
from datetime import date, datetime
from typing import Iterator, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models.event_study import EventRecord, EventStudyResult, EventSummary
from models.filing import Filing
from web.routers.event_study import router as event_study_router
from services.plan_service import PlanContext, PlanQuota
from web.deps import get_plan_context


@pytest.fixture()
def event_study_client(db_session: Session) -> Iterator[Tuple[TestClient, Session]]:
    app = FastAPI()
    app.include_router(event_study_router, prefix="/api/v1")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    plan_context = PlanContext(
        tier="enterprise",
        base_tier="enterprise",
        expires_at=None,
        entitlements=frozenset({"timeline.full"}),
        quota=PlanQuota(
            chat_requests_per_day=None,
            rag_top_k=None,
            self_check_enabled=True,
            peer_export_row_limit=None,
        ),
    )

    app.dependency_overrides[get_plan_context] = lambda: plan_context
    client = TestClient(app)
    try:
        yield client, db_session
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_plan_context, None)


def seed_event_data(session: Session) -> None:
    session.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS market_cap NUMERIC"))
    session.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS cap_bucket TEXT"))
    session.execute(text("ALTER TABLE event_summary ADD COLUMN IF NOT EXISTS cap_bucket TEXT DEFAULT 'ALL'"))
    session.commit()
    filing = Filing(
        id=uuid.uuid4(),
        corp_code="00123456",
        corp_name="삼성전자",
        ticker="005930",
        market="KOSPI",
        title="자사주 매입",
        report_name="주요사항보고서",
        receipt_no="RCP001",
        filed_at=datetime(2025, 1, 3),
        urls={"viewer": "https://dart.example/RCP001"},
    )
    filing2 = Filing(
        id=uuid.uuid4(),
        corp_code="00987654",
        corp_name="카카오",
        ticker="035720",
        market="KOSDAQ",
        title="배당 결정",
        report_name="임시공시",
        receipt_no="RCP002",
        filed_at=datetime(2025, 1, 5),
    )
    session.add_all([filing, filing2])

    event = EventRecord(
        rcept_no="RCP001",
        corp_code="00123456",
        corp_name="삼성전자",
        ticker="005930",
        event_type="BUYBACK",
        event_date=date(2025, 1, 3),
        amount=1_000_000_000.0,
        ratio=0.02,
        method="open_market",
        score=0.72,
        source_url="https://dart.example/RCP001",
        market_cap=5_000_000_000_000,
        cap_bucket="LARGE",
    )
    event2 = EventRecord(
        rcept_no="RCP002",
        corp_code="00987654",
        corp_name="카카오",
        ticker="035720",
        event_type="DIVIDEND",
        event_date=date(2025, 1, 5),
        amount=500_000_000.0,
        ratio=0.01,
        method="cash",
        score=0.45,
        market_cap=800_000_000_000,
        cap_bucket="MID",
    )
    session.add_all([event, event2])

    summary = EventSummary(
        asof=date(2025, 1, 10),
        event_type="BUYBACK",
        window="[-5,20]",
        scope="market",
        cap_bucket="ALL",
        filters=None,
        n=24,
        hit_rate=0.58,
        mean_caar=0.012,
        ci_lo=0.004,
        ci_hi=0.02,
        p_value=0.03,
        aar=[{"t": 0, "aar": 0.001}],
        caar=[{"t": 0, "caar": 0.001}],
        dist=[{"bin": 0, "range": [-0.01, 0.0], "count": 3}],
    )
    summary2 = EventSummary(
        asof=date(2025, 1, 10),
        event_type="DIVIDEND",
        window="[-5,20]",
        scope="market",
        cap_bucket="ALL",
        filters=None,
        n=12,
        hit_rate=0.4,
        mean_caar=-0.004,
        ci_lo=-0.01,
        ci_hi=0.003,
        p_value=0.2,
        aar=[{"t": 0, "aar": -0.0005}],
        caar=[{"t": 0, "caar": -0.0005}],
        dist=[],
    )
    session.add_all([summary, summary2])

    for t in range(-2, 3):
        session.add(
            EventStudyResult(
                rcept_no="RCP001",
                t=t,
                ar=0.001 * (t + 3),
                car=0.0015 * (t + 3),
            )
        )
    session.add(
        EventStudyResult(
            rcept_no="RCP002",
            t=10,
            ar=-0.002,
            car=-0.004,
        )
    )
    session.commit()


def test_event_study_summary_filters_significance(event_study_client):
    client, session = event_study_client
    seed_event_data(session)

    response = client.get("/api/v1/event-study/summary", params={"eventTypes": "BUYBACK", "start": -5, "end": 20, "sig": 0.05})
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["eventType"] == "BUYBACK"
    assert payload["results"][0]["hitRate"] == pytest.approx(0.58)
    assert payload["results"][0]["capBucket"] == "ALL"

    # Dividends should be filtered out due to high p-value when requesting all types
    response_all = client.get("/api/v1/event-study/summary", params={"start": -5, "end": 20, "sig": 0.05})
    types = [item["eventType"] for item in response_all.json()["results"]]
    assert "DIVIDEND" not in types

    response_mid = client.get("/api/v1/event-study/summary", params={"start": -5, "end": 20, "capBuckets": "MID"})
    assert response_mid.status_code == 200
    for item in response_mid.json()["results"]:
        assert item["capBucket"] == "MID"


def test_event_study_events_listing(event_study_client):
    client, session = event_study_client
    seed_event_data(session)

    response = client.get(
        "/api/v1/event-study/events",
        params={
            "markets": "KOSPI",
            "eventTypes": "BUYBACK",
            "windowEnd": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["events"][0]["corpName"] == "삼성전자"
    assert payload["events"][0]["caar"] is not None
    assert payload["events"][0]["capBucket"] == "LARGE"

    cap_filtered = client.get(
        "/api/v1/event-study/events",
        params={
            "capBuckets": "MID",
            "windowEnd": 2,
        },
    )
    assert cap_filtered.status_code == 200
    cap_payload = cap_filtered.json()
    assert cap_payload["total"] == 1
    assert cap_payload["events"][0]["capBucket"] == "MID"


def test_event_study_event_detail(event_study_client):
    client, session = event_study_client
    seed_event_data(session)

    response = client.get("/api/v1/event-study/events/RCP001", params={"start": -2, "end": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["receiptNo"] == "RCP001"
    assert len(payload["series"]) == 5
    assert payload["capBucket"] == "LARGE"
    assert payload["marketCap"] == pytest.approx(5_000_000_000_000)
