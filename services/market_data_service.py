"""Market data client for public data portal (stock price + financial summary)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StockPrice(BaseModel):
    basDt: str = Field(description="기준일자, e.g., 20231120")
    clpr: float = Field(description="종가")


class FinancialMetric(BaseModel):
    label: str
    value: str


API_KEY = os.getenv("DATA_GO_API_KEY")
PRICE_ENDPOINT = "https://api.odcloud.kr/api/GetStockSecuritiesInfoService/v1/getStockPriceInfo"
FINANCIAL_BASE = "https://apis.data.go.kr/1160100/service/GetFinaStatInfoService_V2"
SUMMARY_PATH = "/getSummFinaStat_V2"


def _safe_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _normalize_items(items: list[dict]) -> List[StockPrice]:
    normalized: List[StockPrice] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        bas_dt = item.get("basDt")
        clpr = _safe_float(item.get("clpr"))
        if not bas_dt or clpr is None:
            continue
        try:
            normalized.append(StockPrice(basDt=str(bas_dt), clpr=clpr))
        except Exception:
            continue
    normalized.sort(key=lambda row: row.basDt)
    return normalized


def get_stock_price_history(ticker_or_name: str, *, period_days: int = 90) -> List[StockPrice]:
    """Fetch recent stock prices by name/code from the public data portal.

    Falls back gracefully with an empty list on any failure.
    """
    if not API_KEY:
        logger.warning("DATA_GO_API_KEY not set; skipping stock price fetch.")
        return []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=max(1, period_days))

    params = {
        "serviceKey": API_KEY,
        "resultType": "json",
        "numOfRows": max(10, period_days),
        "pageNo": 1,
        # API supports 검색 by 종목명; 추후 코드 기반 검색으로 보완 가능
        "likeItmsNm": ticker_or_name,
        "beginBasDt": start_date.strftime("%Y%m%d"),
        "endBasDt": end_date.strftime("%Y%m%d"),
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(3.0, connect=2.0)) as client:
            response = client.get(PRICE_ENDPOINT, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Stock price fetch failed for %s: %s", ticker_or_name, exc)
        return []

    items = (
        payload.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
        if isinstance(payload, dict)
        else []
    )
    if not isinstance(items, list):
        logger.debug("Unexpected items type from stock API: %s", type(items))
        return []

    return _normalize_items(items)


def get_financials_summary(crno: str, biz_year: Optional[str] = None, *, rows: int = 10) -> List[FinancialMetric]:
    """Fetch summary financials for a corporation registration number and biz year."""

    if not API_KEY:
        logger.warning("DATA_GO_API_KEY not set; skipping financial summary fetch.")
        return []

    target_year = biz_year or str(datetime.now().year - 1)
    params = {
        "serviceKey": API_KEY,
        "resultType": "json",
        "pageNo": 1,
        "numOfRows": max(1, rows),
        "crno": crno,
        "bizYear": target_year,
    }

    url = f"{FINANCIAL_BASE}{SUMMARY_PATH}"

    try:
        with httpx.Client(timeout=httpx.Timeout(3.0, connect=2.0)) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Financial summary fetch failed for crno=%s, year=%s: %s", crno, target_year, exc)
        return []

    items = (
        payload.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
        if isinstance(payload, dict)
        else []
    )
    if not isinstance(items, list):
        logger.debug("Unexpected financial summary items type: %s", type(items))
        return []
    if not items:
        return []

    item = items[0] if isinstance(items[0], dict) else {}
    metrics: List[FinancialMetric] = []

    def _add(label: str, key: str) -> None:
        value = item.get(key)
        if value not in (None, ""):
            metrics.append(FinancialMetric(label=label, value=str(value)))

    _add("매출액", "enpSaleAmt")
    _add("영업이익", "enpBzopPft")
    _add("당기순이익", "enpCrtmNpf")
    _add("총자산", "enpTastAmt")
    _add("총부채", "enpTdbtAmt")
    _add("총자본", "enpTcptAmt")
    _add("자본금", "enpCptlAmt")
    _add("부채비율", "fnclDebtRto")

    return metrics


__all__ = [
    "StockPrice",
    "FinancialMetric",
    "get_stock_price_history",
    "get_financials_summary",
]
