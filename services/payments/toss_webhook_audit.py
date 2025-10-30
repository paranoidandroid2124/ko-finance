"""Toss 웹훅 감사 로그 저장/조회 유틸리티."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Type, TYPE_CHECKING, cast

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_AUDIT_LOG_PATH = Path("uploads") / "admin" / "toss_webhook_audit.jsonl"
_MAX_PERSISTED_ENTRIES = 1000

try:  # pragma: no cover - DB 초기화 실패 시 파일 기반으로만 동작
    from database import SessionLocal as _SessionLocal
    from models.payments import TossWebhookEventLog as _TossWebhookEventLog
    from sqlalchemy.exc import SQLAlchemyError as _SQLAlchemyError
except Exception:  # pragma: no cover
    _SessionLocal = None
    _TossWebhookEventLog = None
    _SQLAlchemyError = Exception

SessionFactory = cast(Optional[Callable[[], "Session"]], _SessionLocal)
TossWebhookEventLogModel = cast(Optional[Type[Any]], _TossWebhookEventLog)
SQLAlchemyError = cast(Type[Exception], _SQLAlchemyError)


def append_webhook_audit_entry(
    *,
    result: str,
    context: Dict[str, Any],
    payload: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> None:
    """웹훅 처리 결과를 감사 로그로 남기고, 가능하다면 DB에도 적재합니다."""
    entry = {
        "loggedAt": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "message": message,
        "context": context,
        "payload": payload,
    }

    _persist_to_db(result=result, context=context, payload=payload, message=message)

    try:
        path = _AUDIT_LOG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, ensure_ascii=False))
            fp.write("\n")
    except OSError as exc:  # pragma: no cover - 파일 접근 실패는 로그만 남기고 무시
        logger.error("Toss 웹훅 감사 로그 파일 기록 실패: %s", exc)
        return

    _truncate_audit_log()


def read_recent_webhook_entries(limit: int = 100) -> Iterable[Dict[str, Any]]:
    """최근 감사 로그 엔트리를 역순으로 반환합니다."""
    db_entries = _fetch_recent_from_db(limit)
    if db_entries is not None:
        return db_entries

    path = _AUDIT_LOG_PATH
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:  # pragma: no cover
        logger.error("Toss 웹훅 감사 로그 파일을 읽을 수 없습니다: %s", exc)
        return []

    recent = lines[-limit:]
    entries: list[Dict[str, Any]] = []
    for line in reversed(recent):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _truncate_audit_log() -> None:
    """로그 파일이 최대 엔트리 수를 초과하면 앞부분을 제거합니다."""
    path = _AUDIT_LOG_PATH
    if not path.exists():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    if len(lines) <= _MAX_PERSISTED_ENTRIES:
        return

    try:
        truncated = lines[-_MAX_PERSISTED_ENTRIES:]
        path.write_text("\n".join(truncated) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        logger.error("Toss 웹훅 감사 로그 파일 축소 실패: %s", exc)


def _persist_to_db(
    *,
    result: str,
    context: Dict[str, Any],
    payload: Optional[Dict[str, Any]],
    message: Optional[str],
) -> None:
    if SessionFactory is None or TossWebhookEventLogModel is None:  # pragma: no cover - DB 미구성
        return

    try:
        session = SessionFactory()
    except Exception as exc:  # pragma: no cover
        logger.debug("Toss 웹훅 감사 로그 DB 세션 생성 실패: %s", exc)
        return

    try:
        record = TossWebhookEventLogModel(
            transmission_id=context.get("transmission_id"),
            order_id=context.get("order_id"),
            event_type=context.get("event_type"),
            status=context.get("status"),
            result=result,
            dedupe_key=context.get("dedupe_key"),
            retry_count=context.get("retry_count"),
            message=message,
            context=context,
            payload=payload,
            processed_at=context.get("processed_at"),
        )
        session.add(record)
        session.commit()
    except SQLAlchemyError as exc:  # pragma: no cover
        session.rollback()
        logger.error("Toss 웹훅 감사 로그 DB 기록 실패: %s", exc)
    finally:
        session.close()


def _fetch_recent_from_db(limit: int) -> Optional[Iterable[Dict[str, Any]]]:
    if SessionFactory is None or TossWebhookEventLogModel is None:  # pragma: no cover
        return None

    try:
        session = SessionFactory()
    except Exception:  # pragma: no cover
        return None

    try:
        rows = (
            session.query(TossWebhookEventLogModel)
            .order_by(TossWebhookEventLogModel.created_at.desc())
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:  # pragma: no cover
        session.close()
        return None
    finally:
        session.close()

    entries: list[Dict[str, Any]] = []
    for row in rows:
        entries.append(
            {
                "loggedAt": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
                "result": row.result,
                "message": row.message,
                "context": row.context or {},
                "payload": row.payload,
            }
        )
    return entries
