"""Factory that orchestrates widget generators for chat answers."""

from __future__ import annotations

from typing import List, Optional, Sequence
import logging

from schemas.api.widgets import WidgetAttachment
from services.widgets.base import BaseWidgetGenerator
from services.widgets.stock_chart import StockChartGenerator
from services.widgets.financial_table import FinancialTableGenerator

logger = logging.getLogger(__name__)

# Register available generators here.
WIDGET_GENERATORS: Sequence[BaseWidgetGenerator] = (
    StockChartGenerator(),
    FinancialTableGenerator(),
)


def generate_widgets(
    question: str,
    answer: str,
    *,
    context: Optional[Sequence[dict]] = None,
) -> List[WidgetAttachment]:
    """Run all applicable generators and collect widget attachments."""

    attachments: List[WidgetAttachment] = []
    for generator in WIDGET_GENERATORS:
        try:
            if not generator.is_applicable(question, answer, context=context):
                continue
            generated = generator.generate(question, answer, context=context) or []
            attachments.extend(generated)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Widget generator '%s' failed: %s", getattr(generator, "name", "unknown"), exc)
            continue
    return attachments


__all__ = ["generate_widgets", "WIDGET_GENERATORS"]
