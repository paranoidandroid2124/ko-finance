"""Lightweight helpers and wrapper class for JSON-backed persistence."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional, Union

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


class JsonStore:
    """Simple cached JSON file wrapper with env override support."""

    def __init__(
        self,
        *,
        path_env: Optional[str],
        default_path: Path,
    ) -> None:
        self._path_env = path_env
        self._default_path = Path(default_path)
        self._cache: Optional[Any] = None

    def _resolve_path(self) -> Path:
        if self._path_env:
            env_value = os.getenv(self._path_env)
            if env_value:
                return Path(env_value).expanduser()
        return self._default_path

    def clear_cache(self) -> None:
        self._cache = None

    def load(
        self,
        *,
        loader: Callable[[Any], Any],
        fallback: Callable[[], Any],
        reload: bool = False,
    ) -> Any:
        if self._cache is not None and not reload:
            return deepcopy(self._cache)

        path = self._resolve_path()
        raw_payload = read_json_document(path, default=fallback)
        merged = loader(raw_payload) if callable(loader) else raw_payload
        self._cache = deepcopy(merged)
        return deepcopy(merged)

    def save(self, payload: Any) -> None:
        path = self._resolve_path()
        write_json_document(path, payload)
        self._cache = deepcopy(payload)


__all__ = [
    "JsonStore",
    "ensure_parent_dir",
    "read_json_document",
    "write_json_document",
]
