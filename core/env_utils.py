"""Helpers for loading optional .env files and validating required variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from dotenv import load_dotenv  # type: ignore

from core.logging import get_logger

logger = get_logger(__name__)


def load_dotenv_if_available(path: Path | None = None) -> None:
    """Load environment variables from a .env file when the file exists."""

    env_path = path or Path(".env")
    try:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            logger.debug("Loaded environment variables from %s", env_path)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to load .env file %s: %s", env_path, exc)


def require_env_vars(required: Sequence[str], *, context: str | None = None) -> None:
    """Raise an error when one or more required environment variables are missing."""

    missing = [name for name in required if not os.getenv(name)]
    if not missing:
        return

    prefix = f"[{context}] " if context else ""
    message = (
        f"{prefix}Missing required environment variables: {', '.join(sorted(missing))}. "
        "Populate your .env or configure runtime secrets."
    )
    raise RuntimeError(message)


__all__ = ["load_dotenv_if_available", "require_env_vars"]

