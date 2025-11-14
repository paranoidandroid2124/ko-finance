"\"\"\"Loader utilities for public EOD price data used by the event study.\"\"\""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import requests
from sqlalchemy import asc
from sqlalchemy.orm import Session

from core.env import env_str
from models.event_study import Price
from services.ingest_errors import FatalIngestError, TransientIngestError

logger = logging.getLogger(__name__)

DATA_API_KEY = env_str("DATA_GO_API_KEY")
STOCK_ENDPOINT = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
ETF_ENDPOINT = "https://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService/getETFPriceInfo"


class MarketDataError(RuntimeError):
    """Raised when the public API returns an error payload."""


def ingest_stock_prices(
    db: Session,
    *,
    symbols: Optional[Iterable[str]] = None,
    start_date: date,
    end_date: date,
) -> int:
    """Fetch stock EOD data. If symbols omitted, ingest all KRX listings per day."""

    symbols_list = list(symbols or [])
    if symbols_list:
        return _ingest_symbol_subset(
            db,
            endpoint=STOCK_ENDPOINT,
            symbols=symbols_list,
            start_date=start_date,
            end_date=end_date,
            benchmark=False,
        )
    return _ingest_full_market(
        db,
        endpoint=STOCK_ENDPOINT,
        start_date=start_date,
        end_date=end_date,
        benchmark=False,
    )


def ingest_etf_prices(
    db: Session,
    *,
    symbols: Optional[Iterable[str]] = None,
    start_date: date,
    end_date: date,
) -> int:
    """Fetch ETF prices. Defaults to full-market ingestion when symbols omitted."""

    symbols_list = list(symbols or [])
    if symbols_list:
        return _ingest_symbol_subset(
            db,
            endpoint=ETF_ENDPOINT,
            symbols=symbols_list,
            start_date=start_date,
            end_date=end_date,
            benchmark=True,
        )
    return _ingest_full_market(
        db,
        endpoint=ETF_ENDPOINT,
        start_date=start_date,
        end_date=end_date,
        benchmark=True,
    )


def _fetch_api(endpoint: str, params: Dict[str, str]) -> Dict[str, any]:
    if not DATA_API_KEY:
        raise FatalIngestError("DATA_GO_API_KEY is not configured.")

    merged = {
        "serviceKey": DATA_API_KEY,
        "resultType": "json",
    }
    merged.update(params)
    try:
        response = requests.get(endpoint, params=merged, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TransientIngestError(f"Failed to call {endpoint}") from exc
    data = response.json()
    result = data.get("response", {}).get("body", {})
    if result.get("totalCount") == 0:
        return {"items": []}
    items = result.get("items", {}).get("item")
    if items is None:
        raise FatalIngestError(f"Unexpected payload from {endpoint}: {data}")
    if not isinstance(items, list):
        items = [items]
    return {"items": items}


def _ingest_symbol_subset(
    db: Session,
    *,
    endpoint: str,
    symbols: Iterable[str],
    start_date: date,
    end_date: date,
    benchmark: bool,
) -> int:
    inserted = 0
    for symbol in symbols:
        payload = _fetch_api(
            endpoint,
            {
                "likeSrtnCd": symbol,
                "beginBasDt": start_date.strftime("%Y%m%d"),
                "endBasDt": end_date.strftime("%Y%m%d"),
                "numOfRows": 5000,
            },
        )
        rows = payload.get("items") or []
        inserted += _upsert_price_rows(
            db,
            rows,
            benchmark=benchmark,
            symbol_override=symbol,
        )
    if inserted:
        db.commit()
    return inserted


def _ingest_full_market(
    db: Session,
    *,
    endpoint: str,
    start_date: date,
    end_date: date,
    benchmark: bool,
) -> int:
    inserted = 0
    current = start_date
    while current <= end_date:
        payload = _fetch_api(
            endpoint,
            {
                "basDt": current.strftime("%Y%m%d"),
                "numOfRows": 10000,
            },
        )
        rows = payload.get("items") or []
        inserted += _upsert_price_rows(
            db,
            rows,
            benchmark=benchmark,
            symbol_override=None,
        )
        current += timedelta(days=1)
    if inserted:
        db.commit()
    return inserted


def _upsert_price_rows(
    db: Session,
    rows: List[Dict[str, any]],
    *,
    benchmark: bool,
    symbol_override: Optional[str],
) -> int:
    inserted = 0
    parsed_rows = []
    for row in rows:
        bas_dt = row.get("basDt")
        symbol = _resolve_symbol(row, symbol_override)
        close = row.get("clpr")
        adj_close = row.get("clpr")
        ret = row.get("fltRt")
        volume = row.get("trqu")
        if not bas_dt or close is None or not symbol:
            continue
        trade_date = datetime.strptime(bas_dt, "%Y%m%d").date()
        parsed_rows.append(
            {
                "symbol": symbol.upper(),
                "date": trade_date,
                "close": float(close),
                "adj_close": float(adj_close),
                "volume": _parse_int(volume),
                "ret": float(ret) / 100.0 if ret not in (None, "") else None,
            }
        )

    parsed_rows.sort(key=lambda entry: entry["date"])
    for entry in parsed_rows:
        record = db.get(Price, (entry["symbol"], entry["date"]))
        if record:
            record.open = entry["adj_close"]
            record.close = entry["close"]
            record.adj_close = entry["adj_close"]
            record.volume = entry["volume"]
            record.ret = entry["ret"]
            record.benchmark = benchmark
        else:
            record = Price(
                symbol=entry["symbol"],
                date=entry["date"],
                open=None,
                high=None,
                low=None,
                close=entry["close"],
                adj_close=entry["adj_close"],
                volume=entry["volume"] if entry["volume"] is not None else None,
                ret=entry["ret"],
                benchmark=benchmark,
            )
            db.add(record)
            inserted += 1
    return inserted


def _resolve_symbol(row: Dict[str, Any], override: Optional[str]) -> Optional[str]:
    if override:
        return override.strip().upper()
    candidate = row.get("srtnCd") or row.get("isinCd")
    if not candidate:
        return None
    candidate = str(candidate).strip().upper()
    if len(candidate) > 6 and candidate.startswith("KR"):
        candidate = candidate[-6:]
    return candidate or None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


__all__ = [
    "ingest_stock_prices",
    "ingest_etf_prices",
    "MarketDataError",
]
