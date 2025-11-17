"""Shared helpers for plan entitlement labels."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

_DEFAULT_LABELS: Dict[str, str] = {
    "search.compare": "비교 검색",
    "search.alerts": "알림 자동화",
    "search.export": "데이터 내보내기",
    "evidence.inline_pdf": "Evidence PDF",
    "evidence.diff": "Evidence Diff",
    "timeline.full": "전체 타임라인",
    "table.explorer": "Table Explorer",
    "collab.notebook": "Research Notebook",
    "reports.event_export": "이벤트 리포트 Export (Pro+)",
}

_LABELS_FILE = Path(
    os.getenv("PLAN_ENTITLEMENT_LABELS_FILE", "web/dashboard/src/data/plan/entitlementLabels.json")
)


@lru_cache(maxsize=1)
def _load_entitlement_labels() -> Dict[str, str]:
    if _LABELS_FILE.exists():
        try:
            data = json.loads(_LABELS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items()}
        except (OSError, ValueError) as exc:
            logger.warning(
                "Failed to load plan entitlement labels from %s: %s. Falling back to defaults.",
                _LABELS_FILE,
                exc,
            )
    return dict(_DEFAULT_LABELS)


def get_entitlement_labels() -> Dict[str, str]:
    """Return a copy of the entitlement label mapping."""

    return dict(_load_entitlement_labels())


def get_entitlement_label(entitlement: str) -> str:
    """Return the friendly label for a specific entitlement."""

    labels = _load_entitlement_labels()
    return labels.get(entitlement, entitlement)


__all__ = ["get_entitlement_label", "get_entitlement_labels"]
