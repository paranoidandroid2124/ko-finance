"""Lightweight stock chart generator (mock data for initial rollout)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional, Sequence
import re

from schemas.api.widgets import LineChartWidget, WidgetAttachment
from services.market_data_service import get_stock_price_history
from services.utils.ticker_extractor import extract_ticker_or_name
from services.widgets.base import BaseWidgetGenerator


class StockChartGenerator(BaseWidgetGenerator):
    name = "stock_chart"

    def is_applicable(self, question: str, answer: str, *, context: Optional[Sequence[dict]] = None) -> bool:
        text = f"{question or ''} {answer or ''}".lower()
        keywords = ("주가", "차트", "시세", "그래프", "가격")
        return any(keyword in text for keyword in keywords)

    def generate(
        self, question: str, answer: str, *, context: Optional[Sequence[dict]] = None
    ) -> Optional[List[WidgetAttachment]]:
        ticker = extract_ticker_or_name(question) or _extract_ticker(question) or "삼성전자"
        prices = get_stock_price_history(ticker, period_days=90)
        if not prices:
            return None

        data = []
        for row in prices:
            # basDt is YYYYMMDD; normalize to ISO date string
            date_text = _normalize_date(row.basDt)
            if not date_text or row.clpr is None:
                continue
            data.append({"date": date_text, "price": row.clpr})

        if not data:
            return None

        widget = LineChartWidget(
            type="line",
            title=f"{ticker} 주가 추이",
            label=f"{ticker} Price",
            unit="KRW",
            data=data,
            description="공공데이터포털 활용",
        )
        return [widget]


def _extract_ticker(text: str) -> Optional[str]:
    """Very lightweight ticker guesser; replace with proper NER later."""
    if not text:
        return None
    # match 6-digit KRX style or uppercase alpha 4-5 chars
    match = re.search(r"\b(\d{6}|[A-Z]{4,5})\b", text.upper())
    if match:
        return match.group(1)
    return None


def _normalize_date(raw: str) -> Optional[str]:
    text = str(raw).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        try:
            parsed = date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
            return parsed.isoformat()
        except ValueError:
            return None
    # Already ISO-like
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None
