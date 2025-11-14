"""Celery worker entrypoint that re-exports the configured app."""

from __future__ import annotations

from .celery_app import app

__all__ = ["app"]
