"""Atomic JSON file helpers to avoid duplicated persistence logic."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from services.admin_shared import ensure_parent_dir


def write_json_atomic(
    path: Path,
    payload: Any,
    *,
    logger: Optional[logging.Logger] = None,
    ensure_ascii: bool = False,
) -> None:
    """Persist ``payload`` to ``path`` using a temp file + atomic rename."""

    ensure_parent_dir(path, logger)
    tmp_file: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=ensure_ascii, indent=2)
            tmp_file = Path(handle.name)
        tmp_file.replace(path)
    except OSError as exc:  # pragma: no cover - logging guard
        if logger:
            logger.error("Failed to persist JSON to %s: %s", path, exc)
        if tmp_file:
            try:
                tmp_file.unlink(missing_ok=True)  # type: ignore[arg-type]
            except OSError:
                pass
        raise


__all__ = ["write_json_atomic"]
