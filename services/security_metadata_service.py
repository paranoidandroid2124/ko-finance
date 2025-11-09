"\"\"\"Sync KRX security metadata and compute market-cap buckets.\"\"\""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

import requests
from sqlalchemy.orm import Session

from core.env import env_str
from models.event_study import EventRecord
from models.security_metadata import SecurityMetadata

logger = logging.getLogger(__name__)

DATA_API_KEY = env_str("DATA_GO_API_KEY")
LISTING_ENDPOINT = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


class SecurityMetadataError(RuntimeError):
    """Raised when the public listing API returns an unexpected payload."""


def sync_security_metadata(db: Session, *, as_of: Optional[date] = None) -> int:
    """Fetch latest listing snapshot (including market cap) and upsert metadata."""

    if not DATA_API_KEY:
        raise SecurityMetadataError("DATA_GO_API_KEY is not configured.")

    target_date = as_of or date.today()
    rows: List[Dict[str, Any]] = []
    attempts = 0
    current = target_date
    while not rows and attempts < 5:
        rows = _fetch_listing_snapshot(current)
        attempts += 1
        if rows:
            logger.info("Fetched %d security metadata rows for %s", len(rows), current)
            break
        current -= timedelta(days=1)
    if not rows:
        logger.warning("No security metadata returned for %s (after %d attempts)", target_date, attempts)
        return 0
    if not rows:
        logger.info("No security metadata rows returned for %s", target_date)
        return 0

    upserted = 0
    for row in rows:
        symbol = _resolve_symbol(row.get("srtnCd") or row.get("isinCd"))
        if not symbol:
            continue
        market = _normalize_market(row.get("mrktCtg"))
        corp_name = row.get("itmsNm") or None
        shares = _parse_int(row.get("lstgStCnt"))
        market_cap = _parse_float(row.get("mrktTotAmt"))

        record = db.get(SecurityMetadata, symbol)
        if record is None:
            record = SecurityMetadata(ticker=symbol)
            db.add(record)
        record.corp_code = row.get("corpCode") or record.corp_code
        record.corp_name = corp_name or record.corp_name
        record.market = market or record.market
        record.shares = shares or record.shares
        record.market_cap = market_cap
        record.extra = (record.extra or {}) | {"as_of": current.isoformat()}
        upserted += 1

    db.commit()
    _assign_cap_buckets(db)
    return upserted


def backfill_event_cap_metadata(db: Session) -> int:
    """Update events missing cap metadata using the latest security metadata."""

    ticker_map = {row.ticker: row for row in db.query(SecurityMetadata).all()}
    rows = (
        db.query(EventRecord)
        .filter(
            EventRecord.ticker.isnot(None),
            (EventRecord.cap_bucket.is_(None)) | (EventRecord.market_cap.is_(None)),
        )
        .all()
    )
    updated = 0
    for event in rows:
        meta = ticker_map.get(event.ticker)
        if not meta:
            continue
        event.market_cap = meta.market_cap
        event.cap_bucket = meta.cap_bucket
        updated += 1
    if updated:
        db.commit()
    return updated


def _fetch_listing_snapshot(target_date: date) -> List[Dict[str, Any]]:
    params = {
        "serviceKey": DATA_API_KEY,
        "resultType": "json",
        "basDt": target_date.strftime("%Y%m%d"),
        "numOfRows": 5000,
        "pageNo": 1,
    }
    rows: List[Dict[str, Any]] = []

    while True:
        response = requests.get(LISTING_ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        body = data.get("response", {}).get("body", {})
        total = body.get("totalCount", 0)
        items = body.get("items", {}).get("item")
        if not items:
            break
        if isinstance(items, list):
            rows.extend(items)
        else:
            rows.append(items)

        if len(rows) >= total:
            break
        params["pageNo"] = params.get("pageNo", 1) + 1

    return rows


def _assign_cap_buckets(db: Session) -> None:
    markets = [value for (value,) in db.query(SecurityMetadata.market).filter(SecurityMetadata.market.isnot(None)).distinct()]
    for market in markets:
        rows = (
            db.query(SecurityMetadata)
            .filter(SecurityMetadata.market == market, SecurityMetadata.market_cap.isnot(None))
            .order_by(SecurityMetadata.market_cap.desc())
            .all()
        )
        total = len(rows)
        if total == 0:
            continue

        large_cut = max(int(total * 0.3), 1)
        mid_cut = max(int(total * 0.4), 1)
        for index, record in enumerate(rows):
            if index < large_cut:
                record.cap_bucket = "LARGE"
            elif index < large_cut + mid_cut:
                record.cap_bucket = "MID"
            else:
                record.cap_bucket = "SMALL"
        db.commit()


def _resolve_symbol(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip().upper()
    if len(candidate) > 6 and candidate.startswith("KR"):
        candidate = candidate[-6:]
    return candidate or None


def _normalize_market(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().upper()
    if "KOSPI" in normalized:
        return "KOSPI"
    if "KOSDAQ" in normalized:
        return "KOSDAQ"
    return normalized


def _parse_int(value: Optional[Any]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _parse_float(value: Optional[Any]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None
