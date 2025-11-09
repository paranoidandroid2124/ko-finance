"""Celery tasks related to watchlist operations."""

from __future__ import annotations

import logging
from typing import Any, Dict

from celery import shared_task

import llm.llm_service as llm_service

logger = logging.getLogger(__name__)


@shared_task(name="watchlist.generate_personal_note")
def generate_watchlist_personal_note_task(prompt_text: str) -> Dict[str, Any]:
    """Background task to generate personalized watchlist notes via LLM."""

    note, metadata = llm_service.generate_watchlist_personal_note(prompt_text)
    usage = (metadata or {}).get("usage") or {}
    logger.info(
        "watchlist.personal_note.task",
        extra={
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "model": metadata.get("model") if metadata else None,
        },
    )
    return {"note": note, "meta": metadata or {}}


__all__ = ["generate_watchlist_personal_note_task"]
