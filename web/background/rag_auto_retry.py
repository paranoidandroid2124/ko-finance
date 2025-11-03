"""Background scheduler that processes automatic RAG reindex retries."""

from __future__ import annotations

import asyncio
from typing import Optional

from core.env import env_bool, env_int, env_str
from core.logging import get_logger
from services import admin_rag_service
from web.routers import admin_rag

logger = get_logger(__name__)

_AUTO_RETRY_ENABLED = env_bool("ADMIN_RAG_AUTO_RETRY_ENABLED", default=True)
_AUTO_RETRY_INTERVAL_SEC = env_int("ADMIN_RAG_AUTO_RETRY_INTERVAL_SECONDS", default=120, minimum=15)
_AUTO_RETRY_ACTOR = env_str("ADMIN_RAG_AUTO_RETRY_ACTOR", "system_auto_retry") or "system_auto_retry"

_auto_retry_task: Optional[asyncio.Task[None]] = None


async def _run_retry_loop() -> None:
    interval = max(_AUTO_RETRY_INTERVAL_SEC, 15)
    while True:
        try:
            await asyncio.to_thread(_process_due_retries)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Automatic RAG retry loop failed: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


def _process_due_retries() -> None:
    due_entries = admin_rag_service.collect_due_retry_entries(
        max_attempts=admin_rag_service.AUTO_RETRY_MAX_ATTEMPTS,
        cooldown_minutes=admin_rag_service.AUTO_RETRY_COOLDOWN_MINUTES,
    )
    if not due_entries:
        return

    for entry in due_entries:
        queue_id = str(entry.get("queueId") or "")
        if not queue_id:
            continue
        status = str(entry.get("status") or "").lower()
        if status in {"running", "retrying"}:
            continue
        scope = str(entry.get("scope") or "")
        sources = admin_rag_service.split_scope_value(scope)
        note = entry.get("note")

        try:
            admin_rag._perform_reindex(  # pylint: disable=protected-access
                actor=_AUTO_RETRY_ACTOR,
                sources=sources,
                note=note,
                queue_id=queue_id,
                retry_entry=entry,
                retry_mode="auto",
                rag_mode="vector",
            )
        except Exception as exc:  # pragma: no cover - errors handled downstream
            logger.warning("Automatic retry for queue %s did not complete: %s", queue_id, exc, exc_info=True)


def start_retry_scheduler() -> None:
    global _auto_retry_task
    if not _AUTO_RETRY_ENABLED:
        logger.info("Automatic RAG retry scheduler disabled via ADMIN_RAG_AUTO_RETRY_ENABLED.")
        return
    if _auto_retry_task and not _auto_retry_task.done():
        return
    loop = asyncio.get_running_loop()
    _auto_retry_task = loop.create_task(_run_retry_loop())


__all__ = ["start_retry_scheduler"]
