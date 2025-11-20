"""Base interfaces for chat widget generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from schemas.api.widgets import WidgetAttachment


class BaseWidgetGenerator(ABC):
    """Contract for adding rich widgets to chat answers."""

    name: str = "base"

    @abstractmethod
    def is_applicable(self, question: str, answer: str, *, context: Optional[Sequence[dict]] = None) -> bool:
        """Return True if this generator should run for the given question/answer."""

    @abstractmethod
    def generate(
        self, question: str, answer: str, *, context: Optional[Sequence[dict]] = None
    ) -> Optional[List[WidgetAttachment]]:
        """Produce widget attachments to render alongside the answer."""

