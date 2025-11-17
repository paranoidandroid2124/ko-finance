import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from database import Base, get_db
from models.event_study import EventRecord, EventStudyResult, EventSummary
from models.filing import Filing
from web.routers.event_study import router as event_study_router
import web.routers.event_study as event_study_module
from services.plan_service import PlanContext, PlanQuota
from services.evidence_package import PackageResult
from web.deps import get_plan_context


class _TestUser(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=True)


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


def test_event_study_export_endpoint(event_study_client, monkeypatch, tmp_path: Path):
    client, session = event_study_client
    seed_event_data(session)

    fake_payload = {
        "report": {"title": "Event Study Report", "generatedAt": "2025-01-01T00:00:00Z", "requestedBy": "qa"},
        "filters": {"windowLabel": "[-5,20]"},
        "metrics": {"sampleSize": 10, "weightedMeanCaar": "+1.20%", "weightedHitRate": "55%", "weightedPValue": "0.0300", "windowEnd": 20},
        "summary": [],
        "events": {"rows": []},
        "series": [],
        "highlights": {},
    }
    monkeypatch.setattr(event_study_module.event_study_report, "build_event_study_report_payload", lambda *args, **kwargs: fake_payload)

    pdf_path = tmp_path / "event_study_report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 stub")
    monkeypatch.setattr(event_study_module.report_renderer, "render_event_study_report", lambda data: pdf_path)

    zip_path = tmp_path / "bundle.zip"
    zip_path.write_bytes(b"PK")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    bundle = PackageResult(
        pdf_path=pdf_path,
        pdf_object="s3://reports/event-study.pdf",
        pdf_url="https://example.com/event-study.pdf",
        zip_path=zip_path,
        zip_object="s3://reports/event-study.zip",
        zip_url="https://example.com/event-study.zip",
        manifest_path=manifest_path,
    )
    monkeypatch.setattr(event_study_module, "make_evidence_bundle", lambda **kwargs: bundle)
    monkeypatch.setattr(event_study_module, "record_audit_event", lambda **kwargs: None)

    response = client.post(
        "/api/v1/event-study/export",
        json={
            "windowStart": -5,
            "windowEnd": 20,
            "eventTypes": ["BUYBACK"],
            "markets": ["KOSPI"],
            "requestedBy": "qa",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["taskId"].startswith("event-study::")
    assert payload["pdfObject"] == "s3://reports/event-study.pdf"
    assert payload["packageUrl"] == "https://example.com/event-study.zip"
