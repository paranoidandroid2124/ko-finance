"""Shared helpers for admin persistence modules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.logging import get_logger

ADMIN_BASE_DIR = Path("uploads") / "admin"

logger = get_logger(__name__)


def ensure_admin_dir(custom_logger=logger) -> Path:
    """Ensure the base admin directory exists and return its path."""
    try:
        ADMIN_BASE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover
        custom_logger.error("Failed to create admin directory: %s", exc)
    return ADMIN_BASE_DIR


def ensure_parent_dir(path: Path, custom_logger=logger) -> None:
    """Ensure the parent directory of ``path`` exists."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover
        custom_logger.error("Failed to prepare parent directory for %s: %s", path, exc)


def now_iso() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 timestamps, returning ``None`` when parsing fails."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
