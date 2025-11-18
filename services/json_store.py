"""Utility helpers for managing JSON-backed admin stores with caching and locking."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar

from filelock import FileLock, Timeout

from core.env import env_int, env_str
from core.logging import get_logger
from services.admin_shared import ensure_parent_dir
from services.file_store import write_json_atomic

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class JsonStore(Generic[T]):
    """File-backed JSON store with optional caching and optimistic locking."""

    path_env: str
    default_path: Path
    lock_timeout_env: str = "JSON_STORE_LOCK_TIMEOUT_SECONDS"
    default_lock_timeout: int = 5

    _path: Optional[Path] = None
    _cache: Optional[T] = None

    def _resolve_path(self) -> Path:
        if self._path is not None:
            return self._path
        env_value = env_str(self.path_env)
        path = Path(env_value) if env_value else self.default_path
        self._path = path
        return path

    def _lock(self, path: Path) -> FileLock:
        timeout = env_int(self.lock_timeout_env, self.default_lock_timeout, minimum=1)
        lock_path = path.with_suffix(path.suffix + ".lock") if path.suffix else path.with_name(f"{path.name}.lock")
        return FileLock(str(lock_path), timeout=timeout)

    def load(
        self,
        *,
        loader: Callable[[Any], T],
        fallback: Callable[[], T],
        reload: bool = False,
        on_error: Optional[Callable[[Path, Exception], None]] = None,
    ) -> T:
        if self._cache is not None and not reload:
            return deepcopy(self._cache)

        path = self._resolve_path()
        lock = self._lock(path)
        try:
            with lock:
                if not path.exists():
                    data = fallback()
                else:
                    try:
                        raw = json.loads(path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, ValueError) as exc:
                        logger.warning("Failed to parse JSON store %s: %s", path, exc)
                        if on_error:
                            on_error(path, exc)
                        data = fallback()
                    else:
                        try:
                            data = loader(raw)
                        except Exception as exc:
                            logger.warning("Validation failed for JSON store %s: %s", path, exc)
                            if on_error:
                                on_error(path, exc)
                            data = fallback()
        except Timeout as exc:
            raise RuntimeError(f"JSON store at {path} is locked; please retry.") from exc

        self._cache = deepcopy(data)
        return deepcopy(data)

    def save(self, payload: T) -> None:
        path = self._resolve_path()
        lock = self._lock(path)
        ensure_parent_dir(path, logger)
        try:
            with lock:
                write_json_atomic(path, payload, logger=logger)
        except Timeout as exc:
            raise RuntimeError(f"JSON store at {path} is locked; please retry.") from exc

        self._cache = deepcopy(payload)

    def clear_cache(self) -> None:
        self._cache = None


__all__ = ["JsonStore"]
