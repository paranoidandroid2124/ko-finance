from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from models.event_study import EventRecord, EventStudyResult, EventSummary
from models.filing import Filing
from services.event_study_report import build_event_study_report_payload


def _seed_event_data(session: Session) -> None:
    filing = Filing(
        id=uuid.uuid4(),
        corp_code="00123456",
        corp_name="삼성전자",
        ticker="005930",
        market="KOSPI",
        title="자사주 매입",
        report_name="주요사항보고서",
        receipt_no="RCP01001",
        filed_at=datetime(2025, 1, 3),
        urls={"viewer": "https://viewer.dart/RCP01001"},
    )
    filing2 = Filing(
        id=uuid.uuid4(),
        corp_code="00987654",
        corp_name="카카오",
        ticker="035720",
        market="KOSDAQ",
        title="배당 결정",
        report_name="임시공시",
        receipt_no="RCP02002",
        filed_at=datetime(2025, 1, 5),
    )
    session.add_all([filing, filing2])

    event = EventRecord(
        rcept_no="RCP01001",
        corp_code="00123456",
        corp_name="삼성전자",
        ticker="005930",
        event_type="BUYBACK",
        event_date=date(2025, 1, 3),
        amount=1_000_000_000.0,
        ratio=0.02,
        method="open_market",
        score=0.72,
        source_url="https://viewer.dart/RCP01001",
        market_cap=5_000_000_000_000,
        cap_bucket="LARGE",
    )
    event2 = EventRecord(
        rcept_no="RCP02002",
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

    summary_buyback = EventSummary(
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
    summary_dividend = EventSummary(
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
    session.add_all([summary_buyback, summary_dividend])

    for t in range(-2, 3):
        session.add(
            EventStudyResult(
                rcept_no="RCP01001",
                t=t,
                ar=0.001 * (t + 3),
                car=0.0015 * (t + 3),
            )
        )
    session.add(
        EventStudyResult(
            rcept_no="RCP02002",
            t=20,
            ar=-0.002,
            car=-0.004,
        )
    )
    session.commit()


def test_build_event_study_report_payload(db_session: Session) -> None:
    _seed_event_data(db_session)

    payload = build_event_study_report_payload(
        db_session,
        window_start=-5,
        window_end=20,
        event_types=["BUYBACK", "DIVIDEND"],
        limit=5,
        requested_by="qa",
    )

    assert payload["report"]["requestedBy"] == "qa"
    assert payload["filters"]["windowLabel"] == "[-5,20]"
    assert payload["metrics"]["sampleSize"] == 24
    assert payload["summary"], "summary rows should not be empty"
    assert payload["events"]["rows"], "events list should include seeded data"
    assert payload["highlights"]["topPositive"] is not None
