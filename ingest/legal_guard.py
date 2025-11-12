"""Runtime helpers to capture robots.txt and ToS compliance metadata."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict
from urllib import robotparser
from urllib.parse import urlparse

from core.env import env_int, env_str

logger = logging.getLogger(__name__)

ROBOTS_URL = env_str("DART_ROBOTS_URL", "https://dart.fss.or.kr/robots.txt") or "https://dart.fss.or.kr/robots.txt"
ROBOTS_TTL_SECONDS = env_int("DART_ROBOTS_TTL_SECONDS", 3600, minimum=60)
ROBOTS_USER_AGENT = env_str("DART_ROBOTS_USER_AGENT", "kfinance-ingest") or "kfinance-ingest"
TOS_VERSION = env_str("DART_VIEWER_TOS_VERSION", "dart-viewer-2024-01") or "dart-viewer-2024-01"

_ROBOTS_PARSER: robotparser.RobotFileParser | None = None
_ROBOTS_REFRESH_AT: float = 0.0
_LOCK = threading.Lock()


def _ensure_robot_parser(now: float) -> robotparser.RobotFileParser | None:
    global _ROBOTS_PARSER, _ROBOTS_REFRESH_AT
    with _LOCK:
        if _ROBOTS_PARSER is not None and now < _ROBOTS_REFRESH_AT:
            return _ROBOTS_PARSER
        parser = robotparser.RobotFileParser()
        parser.set_url(ROBOTS_URL)
        try:
            parser.read()
            _ROBOTS_PARSER = parser
            _ROBOTS_REFRESH_AT = now + float(ROBOTS_TTL_SECONDS)
            logger.debug("Refreshed robots.txt from %s (ttl=%ss).", ROBOTS_URL, ROBOTS_TTL_SECONDS)
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("Unable to refresh robots.txt (%s): %s", ROBOTS_URL, exc)
            _ROBOTS_PARSER = None
            _ROBOTS_REFRESH_AT = now + float(ROBOTS_TTL_SECONDS)
        return _ROBOTS_PARSER


def evaluate_viewer_access(viewer_url: str, *, now: float | None = None) -> Dict[str, object]:
    """Return metadata describing robots/ToS compliance for a viewer URL."""
    current_ts = now if now is not None else datetime.now(tz=timezone.utc).timestamp()
    parser = _ensure_robot_parser(current_ts)
    parsed = urlparse(viewer_url)
    path = parsed.path or "/"

    robots_allowed: bool | None = None
    if parser is not None:
        try:
            robots_allowed = parser.can_fetch(ROBOTS_USER_AGENT, viewer_url)
        except Exception as exc:  # pragma: no cover - robot parser edge case
            logger.debug("Robots parser exception for %s: %s", viewer_url, exc)
            robots_allowed = None

    metadata: Dict[str, object] = {
        "viewer_url": viewer_url,
        "viewer_path": path,
        "robots_url": ROBOTS_URL,
        "robots_user_agent": ROBOTS_USER_AGENT,
        "robots_allowed": robots_allowed,
        "robots_checked_at": datetime.fromtimestamp(current_ts, tz=timezone.utc).isoformat(),
        "tos_version": TOS_VERSION,
    }
    return metadata


__all__ = ["evaluate_viewer_access", "ROBOTS_URL", "ROBOTS_USER_AGENT", "TOS_VERSION"]

