"""Lightweight snapshot retrieval facade."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.logging import get_logger
from parse.celery_app import app
from services import chat_service
from web.routers.company import company_snapshot

logger = get_logger(__name__)


def get_company_snapshot(identifier: str, db: Session) -> Dict[str, Any]:
    """Fetch company snapshot by ticker/corp_code (reusing existing router logic)."""
    try:
        # Reuse existing router logic with the provided DB session.
        return company_snapshot(identifier, db=db)  # type: ignore[return-value]
    except HTTPException:
        raise
    except Exception as exc:
        raise RuntimeError(f"snapshot_failed: {exc}") from exc


def _persist_snapshot_success(
    db: Session,
    *,
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    ticker: str,
    snapshot: Dict[str, Any],
    idempotency_key: Optional[str],
) -> None:
    chat_service.create_tool_output_message(
        db,
        session_id=session_id,
        turn_id=turn_id,
        tool_name="snapshot.company",
        output=snapshot or {},
        status="ok",
        idempotency_key=idempotency_key,
    )
    chat_service.update_message_state(
        db,
        message_id=assistant_message_id,
        state="ready",
        content="기업 스냅샷을 준비했습니다.",
        meta={
            "tool_output": {"name": "snapshot.company", "status": "ok"},
            "toolAttachments": [
                {"type": "summary", "title": snapshot.get("corp_name") or ticker, "value": "snapshot_ready"}
            ],
        },
    )
    db.commit()


def _persist_snapshot_error(
    db: Session,
    *,
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    error_message: str,
) -> None:
    chat_service.create_tool_output_message(
        db,
        session_id=session_id,
        turn_id=turn_id,
        tool_name="snapshot.company",
        output={"error": error_message},
        status="error",
        idempotency_key=None,
    )
    chat_service.update_message_state(
        db,
        message_id=assistant_message_id,
        state="error",
        error_code="tool_error",
        error_message=error_message,
        meta={"tool_output": {"name": "snapshot.company", "status": "error", "message": error_message}},
    )
    db.commit()


def run_snapshot_flow(
    db: Session,
    *,
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    ticker: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute snapshot retrieval and persist tool_output + assistant update."""

    try:
        snapshot = get_company_snapshot(ticker, db=db)
    except Exception as exc:
        logger.warning("Snapshot tool failed for %s: %s", ticker, exc, exc_info=True)
        safe_message = "기업 스냅샷을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
        _persist_snapshot_error(
            db,
            session_id=session_id,
            turn_id=turn_id,
            assistant_message_id=assistant_message_id,
            error_message=safe_message,
        )
        return {"status": "error", "message": safe_message}

    _persist_snapshot_success(
        db,
        session_id=session_id,
        turn_id=turn_id,
        assistant_message_id=assistant_message_id,
        ticker=ticker,
        snapshot=snapshot,
        idempotency_key=idempotency_key,
    )
    return {"status": "ok"}


def enqueue_company_snapshot_job(
    *,
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    user_message_id: Optional[uuid.UUID],
    ticker: str,
    idempotency_key: Optional[str],
    db: Session,
) -> str:
    """Enqueue the snapshot tool to run asynchronously; fallback to inline on failure."""

    payload = {
        "session_id": str(session_id),
        "turn_id": str(turn_id),
        "assistant_message_id": str(assistant_message_id),
        "user_message_id": str(user_message_id) if user_message_id else None,
        "ticker": ticker,
        "idempotency_key": idempotency_key,
    }
    try:
        app.send_task("rag.snapshot.company", args=[payload])
        return "queued"
    except Exception as exc:
        logger.warning("Celery unavailable; running snapshot inline (ticker=%s): %s", ticker, exc, exc_info=True)
        run_snapshot_flow(
            db,
            session_id=session_id,
            turn_id=turn_id,
            assistant_message_id=assistant_message_id,
            ticker=ticker,
            idempotency_key=idempotency_key,
        )
        return "inline"


__all__ = ["get_company_snapshot", "run_snapshot_flow", "enqueue_company_snapshot_job"]
