"""Financial table widget generator using public data portal."""

from __future__ import annotations

from typing import List, Optional, Sequence

from schemas.api.widgets import FinancialTableWidget, WidgetAttachment
from services.market_data_service import get_financials_summary
from services.utils.ticker_extractor import extract_ticker_or_name, resolve_crno
from services.widgets.base import BaseWidgetGenerator


class FinancialTableGenerator(BaseWidgetGenerator):
    name = "financial_table"

    KEYWORDS = ("실적", "재무", "매출", "영업이익", "순이익", "손익")

    def is_applicable(self, question: str, answer: str, *, context: Optional[Sequence[dict]] = None) -> bool:
        text = f"{question or ''} {answer or ''}".lower()
        return any(keyword in text for keyword in self.KEYWORDS)

    def generate(
        self, question: str, answer: str, *, context: Optional[Sequence[dict]] = None
    ) -> Optional[List[WidgetAttachment]]:
        ticker = extract_ticker_or_name(question)
        if not ticker:
            return None

        crno = resolve_crno(question) or resolve_crno(ticker) or ticker  # TODO: map ticker->crno via metadata
        metrics = get_financials_summary(crno)
        if not metrics:
            return None

        headers = ["항목", "값"]
        rows = [[metric.label, metric.value] for metric in metrics]
        widget = FinancialTableWidget(
            type="financials",
            title=f"{ticker} 재무 요약",
            headers=headers,
            rows=rows,
            description="공공데이터포털 재무 요약",
        )
        return [widget]


__all__ = ["FinancialTableGenerator"]
