"""CLI helpers to inspect and requeue ingest dead-letter entries."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from scripts._path import add_root

add_root()

from core.env_utils import load_dotenv_if_available  # noqa: E402

load_dotenv_if_available()

from database import SessionLocal  # noqa: E402
from services.ingest_dlq_service import (  # noqa: E402
    get_dead_letter,
    list_dead_letters,
    mark_completed,
    mark_requeued,
    refresh_metrics,
)

logger = logging.getLogger(__name__)


def _parse_status(value: Optional[str]) -> Optional[str]:
    if not value or value.lower() == "all":
        return None
    normalized = value.lower()
    if normalized not in {"pending", "requeued", "completed"}:
        raise argparse.ArgumentTypeError(f"Unknown status '{value}'.")
    return normalized


def _format_letter(letter) -> str:
    payload_hint: str
    if isinstance(letter.payload, Mapping) and letter.payload:
        keys = ", ".join(sorted(letter.payload.keys())[:4])
        payload_hint = f"payload_keys=[{keys}]"
    else:
        payload_hint = "payload_keys=[]"
    return (
        f"{letter.id} | {letter.status.upper():<9} | task={letter.task_name} "
        f"| receipt={letter.receipt_no or '-'} | retries={letter.retries} "
        f"| last_error={letter.last_error_at} | {payload_hint}"
    )


def _safe_payload(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, Mapping) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _enqueue_letter(letter) -> bool:
    task_name = (letter.task_name or "").lower()
    if task_name == "m1.process_filing":
        try:
            from parse.tasks import process_filing  # noqa: WPS433
        except Exception as exc:  # pragma: no cover - import guard
            logger.error("Unable to import process_filing task: %s", exc)
            return False

        payload = _safe_payload(letter.payload)
        filing_id = (
            payload.get("filing_id")
            or payload.get("filingId")
            or payload.get("id")
            or letter.receipt_no
        )
        if not filing_id:
            logger.error(
                "Cannot enqueue m1.process_filing for DLQ entry %s: missing filing_id/receipt_no.",
                letter.id,
            )
            return False
        if hasattr(process_filing, "delay"):
            process_filing.delay(str(filing_id))
            return True
        logger.error("process_filing task does not expose delay(); skipping enqueue.")
        return False

    logger.info("No enqueue mapping defined for task '%s'.", letter.task_name)
    return False


def _handle_list(session, args) -> None:
    letters = list_dead_letters(
        session,
        status=args.status,
        task_name=args.task_name,
        limit=args.limit,
    )
    if not letters:
        print("No DLQ entries match the provided filters.")
        return
    for letter in letters:
        print(_format_letter(letter))


def _handle_show(session, args) -> None:
    letter = get_dead_letter(session, args.letter_id)
    if not letter:
        print(f"DLQ entry {args.letter_id} not found.")
        return
    payload = {
        "id": str(letter.id),
        "task_name": letter.task_name,
        "status": letter.status,
        "receipt_no": letter.receipt_no,
        "corp_code": letter.corp_code,
        "ticker": letter.ticker,
        "payload": letter.payload,
        "error": letter.error,
        "retries": letter.retries,
        "next_run_at": letter.next_run_at.isoformat() if letter.next_run_at else None,
        "created_at": letter.created_at.isoformat() if letter.created_at else None,
        "updated_at": letter.updated_at.isoformat() if letter.updated_at else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _handle_requeue(session, args) -> None:
    letter = get_dead_letter(session, args.letter_id)
    if not letter:
        print(f"DLQ entry {args.letter_id} not found.")
        return
    mark_requeued(session, letter, next_run_at=datetime.now(timezone.utc))
    print(f"Marked {letter.id} as requeued.")
    if args.enqueue:
        if _enqueue_letter(letter):
            print("Celery task enqueued.")
        else:
            print("Unable to enqueue task automatically; please trigger manually.")


def _handle_complete(session, args) -> None:
    letter = get_dead_letter(session, args.letter_id)
    if not letter:
        print(f"DLQ entry {args.letter_id} not found.")
        return
    mark_completed(session, letter)
    print(f"Marked {letter.id} as completed.")


def _handle_refresh_metrics(session) -> None:
    refresh_metrics(session)
    print("DLQ metrics refreshed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and requeue ingest dead-letter entries.")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO).")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List DLQ entries.")
    list_parser.add_argument(
        "--status",
        default="pending",
        help="Filter by status (pending, requeued, completed, all). Default: pending.",
    )
    list_parser.add_argument("--task-name", default=None, help="Filter by Celery task name.")
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum rows to display (default: 20).")

    show_parser = subparsers.add_parser("show", help="Show a DLQ entry as JSON.")
    show_parser.add_argument("letter_id", help="Dead-letter UUID.")

    requeue_parser = subparsers.add_parser("requeue", help="Mark a DLQ entry as requeued.")
    requeue_parser.add_argument("letter_id", help="Dead-letter UUID.")
    requeue_parser.add_argument(
        "--enqueue",
        action="store_true",
        help="Attempt to enqueue the associated Celery task after marking as requeued.",
    )

    complete_parser = subparsers.add_parser("complete", help="Mark a DLQ entry as completed.")
    complete_parser.add_argument("letter_id", help="Dead-letter UUID.")

    subparsers.add_parser("refresh-metrics", help="Force-refresh DLQ Prometheus gauges.")

    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    session = SessionLocal()
    try:
        if args.command == "list":
            args.status = _parse_status(args.status)
            _handle_list(session, args)
            return
        if args.command == "show":
            _handle_show(session, args)
            return
        if args.command == "requeue":
            _handle_requeue(session, args)
            return
        if args.command == "complete":
            _handle_complete(session, args)
            return
        if args.command == "refresh-metrics":
            _handle_refresh_metrics(session)
            return
        parser.error(f"Unknown command {args.command}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
