"""Lightweight helpers for JSON-backed persistence shared across services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Union

JsonDefault = Union[Any, Callable[[], Any]]


def ensure_parent_dir(path: Path) -> None:
    """Ensure ``path`` can be read/written by creating the parent dir."""
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json_document(path: Path, *, default: JsonDefault) -> Any:
    """Return JSON payload stored at ``path`` (or ``default`` if missing/invalid)."""
    ensure_parent_dir(path)
    if not path.exists():
        return default() if callable(default) else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default() if callable(default) else default


def write_json_document(path: Path, payload: Any) -> None:
    """Persist ``payload`` as JSON to ``path``."""
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["ensure_parent_dir", "read_json_document", "write_json_document"]
