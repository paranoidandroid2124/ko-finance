"""Lightweight JSON list store with on-disk persistence + simple caching."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence


class JsonStateStore:
    """Persist small JSON lists with minimal caching."""

    def __init__(self, path: Path, root_key: str, *, logger: Optional[logging.Logger] = None) -> None:
        self._path = Path(path)
        self._root_key = root_key
        self._cache: Optional[List[Mapping[str, Any]]] = None
        self._cache_path: Optional[Path] = None
        self._logger = logger or logging.getLogger(__name__)

    def load(self, *, reload: bool = False) -> List[Mapping[str, Any]]:
        """Load the JSON list as dictionaries."""

        if reload or self._cache is None or self._cache_path != self._path:
            try:
                raw = self._path.read_text(encoding="utf-8")
                payload = json.loads(raw)
                items = payload.get(self._root_key, [])
                if not isinstance(items, list):
                    raise ValueError("root is not a list")
            except FileNotFoundError:
                items = []
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                self._logger.warning("Failed to load state from %s: %s", self._path, exc)
                items = []
            self._cache = [dict(item) for item in items if isinstance(item, Mapping)]
            self._cache_path = self._path

        return [dict(item) for item in self._cache]

    def store(self, items: Sequence[Mapping[str, Any]]) -> None:
        """Persist ``items`` to disk."""

        payload = {self._root_key: [dict(item) for item in items]}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache = [dict(item) for item in items]
        self._cache_path = self._path

    def reset(self, *, path: Optional[Path] = None) -> None:
        """Clear cached state and optionally repoint the underlying file."""

        if path is not None:
            self._path = Path(path)
        self._cache = None
        self._cache_path = None


__all__ = ["JsonStateStore"]
