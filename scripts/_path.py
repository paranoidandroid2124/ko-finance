"""Utilities for adjusting import paths when running scripts directly."""

from __future__ import annotations

import sys
from pathlib import Path


def add_root() -> None:
    """Prepend the repository root to ``sys.path`` if it is missing."""

    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
