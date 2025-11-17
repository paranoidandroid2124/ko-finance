"""Render HTML email bodies for digest experiences."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from core.logging import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "digest"

_EMAIL_ENV: Optional[Environment] = None


def _get_email_env() -> Environment:
    global _EMAIL_ENV
    if _EMAIL_ENV is None:
        _EMAIL_ENV = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _EMAIL_ENV


def _render_template(name: str, context: Mapping[str, Any]) -> str:
    try:
        template = _get_email_env().get_template(name)
    except TemplateNotFound as exc:  # pragma: no cover - deployment guard
        raise RuntimeError(f"Digest template '{name}' not found.") from exc
    return template.render(**context)


def render_watchlist_digest_email(payload: Mapping[str, Any]) -> str:
    """Render the watchlist digest payload into an HTML email."""

    summary = payload.get("summary") or {}
    context: MutableMapping[str, Any] = {
        "generated_at": payload.get("generatedAt"),
        "window_start": summary.get("windowStart"),
        "window_end": summary.get("windowEnd"),
        "window_minutes": payload.get("windowMinutes"),
        "summary": summary,
        "items": payload.get("items") or [],
        "llm_overview": payload.get("llmOverview"),
        "llm_personal_note": payload.get("llmPersonalNote"),
    }
    return _render_template("watchlist.html.jinja", context)


def render_daily_digest_email(payload: Mapping[str, Any]) -> Optional[str]:
    """Render the daily/weekly digest preview to HTML."""

    try:
        context: MutableMapping[str, Any] = {
            "timeframe": payload.get("timeframe") or "daily",
            "period_label": payload.get("periodLabel"),
            "generated_label": payload.get("generatedAtLabel"),
            "source_label": payload.get("sourceLabel"),
            "news": payload.get("news") or [],
            "watchlist": payload.get("watchlist") or [],
            "sentiment": payload.get("sentiment"),
            "actions": payload.get("actions") or [],
            "llm_overview": payload.get("llmOverview"),
            "llm_personal_note": payload.get("llmPersonalNote"),
        }
        return _render_template("daily.html.jinja", context)
    except Exception as exc:  # pragma: no cover - best effort render
        logger.warning("Digest email render failed: %s", exc, exc_info=True)
        return None


__all__ = ["render_daily_digest_email", "render_watchlist_digest_email"]
