"""Backward compatible auth service exports."""

from __future__ import annotations

import services.auth as _auth
from services.auth import *  # noqa: F401,F403

__all__ = _auth.__all__  # type: ignore[attr-defined]
