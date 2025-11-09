from datetime import date, timedelta
from typing import Iterator, List, Tuple

import pytest
from sqlalchemy.orm import Session

from models.event_study import EventRecord, EventStudyResult, Price
from services import event_study_service, market_data_service


@pytest.fixture()
def session_copy(db_session: Session) -> Iterator[Session]:
    """Provide a clean session per test to avoid crosstalk."""

    yield db_session


def _make_api_rows(days: List[Tuple[str, str, str, str]]):
    return [{"basDt": d, "clpr": close, "fltRt": ret, "trqu": vol} for d, close, ret, vol in days]


def _make_full_rows(trade_date: str):
    return [
        {"basDt": trade_date, "srtnCd": "005930", "clpr": "70000", "fltRt": "0.50", "trqu": "1,000"},
        {"basDt": trade_date, "srtnCd": "000660", "clpr": "120000", "fltRt": "-0.20", "trqu": "2,000"},
    ]


def test_ingest_stock_prices_upserts_rows(monkeypatch, session_copy: Session):
    monkeypatch.setattr(market_data_service, "DATA_API_KEY", "test-key")

    first_rows = _make_api_rows(
        [
            ("20240102", "72000", "1.23", "12,345"),
            ("20240103", "72500", "-0.80", "10,000"),
        ]
    )
    monkeypatch.setattr(market_data_service, "_fetch_api", lambda *_args, **_kwargs: {"items": first_rows})

    inserted = market_data_service.ingest_stock_prices(
        session_copy,
        symbols=["005930"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
    )
    assert inserted == 2

    stored = (
        session_copy.query(Price)
        .filter(Price.symbol == "005930")
        .order_by(Price.date.asc())
        .all()
    )
    assert len(stored) == 2
    assert float(stored[0].ret) == pytest.approx(0.0123)
    assert stored[0].volume == 12345

    # Re-run with changed prices to ensure upsert updates existing rows without creating duplicates.
    updated_rows = _make_api_rows(
        [
            ("20240102", "73000", "0.50", "15,000"),
            ("20240103", "73500", "0.10", "11,000"),
        ]
    )
    monkeypatch.setattr(market_data_service, "_fetch_api", lambda *_args, **_kwargs: {"items": updated_rows})
    inserted_again = market_data_service.ingest_stock_prices(
        session_copy,
        symbols=["005930"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
    )
    assert inserted_again == 0

    refreshed = (
        session_copy.query(Price)
        .filter(Price.symbol == "005930")
        .order_by(Price.date.asc())
        .all()
    )
    assert float(refreshed[0].close) == 73000.0
    assert float(refreshed[1].ret) == pytest.approx(0.001)
    assert refreshed[0].volume == 15000


def test_ingest_stock_prices_full_market(monkeypatch, session_copy: Session):
    monkeypatch.setattr(market_data_service, "DATA_API_KEY", "test-key")
    captured_dates: List[str] = []

    def fake_fetch(endpoint, params):
        captured_dates.append(params["basDt"])
        return {"items": _make_full_rows(params["basDt"])}

    monkeypatch.setattr(market_data_service, "_fetch_api", fake_fetch)
    inserted = market_data_service.ingest_stock_prices(
        session_copy,
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
    )
    assert inserted == 4  # 2 days * 2 symbols
    assert captured_dates == ["20240102", "20240103"]

    rows = (
        session_copy.query(Price)
        .filter(Price.date.in_([date(2024, 1, 2), date(2024, 1, 3)]))
        .order_by(Price.symbol.asc(), Price.date.asc())
        .all()
    )
    symbols = {row.symbol for row in rows}
    assert symbols == {"005930", "000660"}
    assert len(rows) == 4


def test_update_event_study_series_generates_ar_car(session_copy: Session):
    symbol = "005930"
    benchmark_symbol = "069500"
    event_day = date(2024, 3, 4)
    estimation_window = (-40, -6)
    event_window = (-2, 2)

    estimation_start = event_day + timedelta(days=estimation_window[0])
    event_end = event_day + timedelta(days=event_window[1])

    current = estimation_start
    idx = 0
    while current <= event_end:
        asset_ret = 0.01 + 0.0001 * idx
        bench_ret = 0.008 + 0.00005 * idx
        session_copy.merge(
            Price(
                symbol=symbol,
                date=current,
                close=100 + idx,
                adj_close=100 + idx,
                volume=1000,
                ret=asset_ret,
                benchmark=False,
            )
        )
        session_copy.merge(
            Price(
                symbol=benchmark_symbol,
                date=current,
                close=50 + idx,
                adj_close=50 + idx,
                volume=500,
                ret=bench_ret,
                benchmark=True,
            )
        )
        current += timedelta(days=1)
        idx += 1
    session_copy.commit()

    event = EventRecord(
        rcept_no="TEST-AR-CAR",
        corp_code="00123456",
        ticker=symbol,
        corp_name="테스트",
        event_type="BUYBACK",
        event_date=event_day,
    )
    session_copy.add(event)
    session_copy.commit()

    created = event_study_service.update_event_study_series(
        session_copy,
        benchmark_symbol=benchmark_symbol,
        estimation_window=estimation_window,
        event_window=event_window,
    )
    assert created == (event_window[1] - event_window[0] + 1)

    rows = (
        session_copy.query(EventStudyResult)
        .filter(EventStudyResult.rcept_no == "TEST-AR-CAR")
        .order_by(EventStudyResult.t.asc())
        .all()
    )
    assert len(rows) == created
    cumulative = 0.0
    for row in rows:
        cumulative += float(row.ar)
        assert float(row.car) == pytest.approx(cumulative, rel=1e-6)
        assert row.t in range(event_window[0], event_window[1] + 1)
