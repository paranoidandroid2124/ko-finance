"""Ingest 13-digit corporation registration numbers (crno) from 금융위 기업기본정보 API into security_metadata."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import func

from database import SessionLocal
from models.security_metadata import SecurityMetadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("DATA_GO_API_KEY")
# Base + default path based on 최신 가이드 (getCorpOutline_V2)
BASE_URL = "https://apis.data.go.kr/1160100/service/GetCorpBasicInfoService_V2"
PATH = os.getenv("CORP_BASIC_INFO_PATH", "/getCorpOutline_V2")
CONCURRENCY = int(os.getenv("CRNO_SYNC_CONCURRENCY", "8"))


def _extract_fields(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (ticker, name, crno) best-effort from an API item."""
    if not isinstance(item, dict):
        return None, None, None

    crno = str(
        item.get("crno")
        or item.get("corpRegNo")
        or item.get("corp_reg_no")
        or item.get("bsprCprRegno")
        or ""
    ).strip()
    name = str(
        item.get("corpName")
        or item.get("corpNm")
        or item.get("corp_name")
        or item.get("corpNmKorean")
        or item.get("cmpyNm")
        or ""
    ).strip()
    ticker = str(
        item.get("stckIssuCmpyCd")
        or item.get("stckIssuCmpyCode")
        or item.get("stckCd")
        or item.get("stock_code")
        or item.get("stkCd")
        or item.get("code")
        or ""
    ).strip()
    return (ticker or None), (name or None), (crno or None)


async def _fetch_crno_async(client: httpx.AsyncClient, ticker: str) -> Tuple[str, Optional[str]]:
    params = {
        "serviceKey": API_KEY,
        "resultType": "json",
        "pageNo": 1,
        "numOfRows": 10,
        "stckCd": ticker,
    }
    url = f"{BASE_URL}{PATH}"
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Fetch failed for %s: %s", ticker, exc)
        return ticker, None

    body = payload.get("response", {}).get("body", {}) if isinstance(payload, dict) else {}
    items = body.get("items", {}).get("item", []) if isinstance(body, dict) else []
    if not items:
        return ticker, None
    if not isinstance(items, list):
        items = [items]

    for item in items:
        _, _, candidate = _extract_fields(item)
        if candidate and len(candidate) == 13:
            return ticker, candidate
    return ticker, None


async def sync_crno_async() -> int:
    if not API_KEY:
        logger.error("DATA_GO_API_KEY not set; aborting.")
        return 0

    session = SessionLocal()
    # Preload tickers we care about (missing crno)
    missing_rows: Dict[str, SecurityMetadata] = {
        ticker: row
        for (ticker, row) in (
            session.query(SecurityMetadata.ticker, SecurityMetadata)
            .filter(SecurityMetadata.ticker.isnot(None))
            .filter((SecurityMetadata.corp_code.is_(None)) | (func.length(SecurityMetadata.corp_code) != 13))
            .all()
        )
    }
    if not missing_rows:
        logger.info("All security_metadata rows already have 13-digit corp_code; nothing to do.")
        session.close()
        return 0
    logger.info("Target tickers missing crno: %s", len(missing_rows))

    updated = 0
    timeout = httpx.Timeout(5.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        semaphore = asyncio.Semaphore(max(1, CONCURRENCY))

        async def runner(tick: str) -> Tuple[str, Optional[str]]:
            async with semaphore:
                return await _fetch_crno_async(client, tick)

        tasks = [runner(t) for t in missing_rows.keys()]
        processed = 0
        for coro in asyncio.as_completed(tasks):
            ticker, crno = await coro
            processed += 1
            if not crno:
                continue
            row = missing_rows.get(ticker)
            if row is None:
                continue
            if row.corp_code != crno:
                row.corp_code = crno
                updated += 1
            missing_rows.pop(ticker, None)

            if updated and updated % 200 == 0:
                session.commit()
                logger.info("Committed %s updates (remaining: %s)", updated, len(missing_rows))
            if not missing_rows:
                logger.info("All target tickers updated; stopping early after %s processed.", processed)
                break

    if updated:
        session.commit()
        logger.info("Updated corp_code (crno) rows: %s (remaining missing: %s)", updated, len(missing_rows))
    else:
        logger.info("No corp_code updates applied.")

    session.close()
    return updated


if __name__ == "__main__":
    asyncio.run(sync_crno_async())
