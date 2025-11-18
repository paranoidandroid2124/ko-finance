"""CLI helpers to inspect and toggle ingest viewer fallback flags."""

from __future__ import annotations

import argparse
import logging
from typing import Any, Iterable, Optional

from scripts._path import add_root

add_root()

from core.env_utils import load_dotenv_if_available  # noqa: E402

load_dotenv_if_available()

from database import SessionLocal  # noqa: E402
from models.ingest_viewer_flag import IngestViewerFlag  # noqa: E402
from services.ingest_policy_service import get_viewer_flag_map  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y"}:
        return True
    if normalized in {"0", "false", "f", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value '{value}'.")


def _format_flag(flag: IngestViewerFlag) -> str:
    enabled = bool(getattr(flag, "fallback_enabled", False))
    status = "ENABLED" if enabled else "DISABLED"
    reason = getattr(flag, "reason", None) or "-"
    updated_by = getattr(flag, "updated_by", None) or "-"
    return f"{flag.corp_code:<10} {status:<8} reason={reason} updated_by={updated_by}"


def _upsert_flag(
    session,
    *,
    corp_code: str,
    enabled: bool,
    reason: Optional[str],
    updated_by: Optional[str],
) -> IngestViewerFlag:
    corp_code = corp_code.strip()
    flag = session.query(IngestViewerFlag).filter_by(corp_code=corp_code).one_or_none()
    if flag is None:
        flag = IngestViewerFlag(
            corp_code=corp_code,
            fallback_enabled=enabled,
            reason=reason,
            updated_by=updated_by,
        )
        session.add(flag)
    else:
        flag.fallback_enabled = enabled
        flag.reason = reason
        if updated_by:
            flag.updated_by = updated_by
    session.commit()
    session.refresh(flag)
    return flag


def _list_flags(session, *, enabled: Optional[bool]) -> Iterable[IngestViewerFlag]:
    query = session.query(IngestViewerFlag)
    if enabled is not None:
        query = query.filter(IngestViewerFlag.fallback_enabled == enabled)
    return query.order_by(IngestViewerFlag.corp_code).all()


def _refresh_cache(session) -> None:
    get_viewer_flag_map(session, force_refresh=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or toggle ingest viewer fallback flags.")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO).")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List all feature flag rows.")
    list_parser.add_argument(
        "--enabled",
        choices=("all", "true", "false"),
        default="all",
        help="Filter by enabled state (default: all).",
    )

    set_parser = subparsers.add_parser("set", help="Upsert a feature flag entry.")
    set_parser.add_argument("corp_code", help="8-digit corp_code value from DART.")
    set_parser.add_argument("--enabled", required=True, type=_parse_bool, help="true/false.")
    set_parser.add_argument("--reason", default=None, help="Optional reason for override.")
    set_parser.add_argument("--updated-by", default=None, help="Operator or system making the change.")

    enable_parser = subparsers.add_parser("enable", help="Shortcut to enable viewer fallback for an issuer.")
    enable_parser.add_argument("corp_code", help="8-digit corp_code value.")
    enable_parser.add_argument("--reason", default=None, help="Optional comment.")
    enable_parser.add_argument("--updated-by", default=None, help="Operator or system reference.")

    disable_parser = subparsers.add_parser("disable", help="Shortcut to disable viewer fallback for an issuer.")
    disable_parser.add_argument("corp_code", help="8-digit corp_code value.")
    disable_parser.add_argument("--reason", default=None, help="Reason for disabling fallback.")
    disable_parser.add_argument("--updated-by", default=None, help="Operator or system reference.")

    subparsers.add_parser("clear-cache", help="Force-refresh the ingest viewer flag cache.")

    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    session = SessionLocal()
    try:
        if args.command == "list":
            enabled_filter: Optional[bool]
            if args.enabled == "all":
                enabled_filter = None
            else:
                enabled_filter = args.enabled == "true"
            flags = _list_flags(session, enabled=enabled_filter)
            if not flags:
                print("No ingest_viewer_flags rows found.")
                return
            for flag in flags:
                print(_format_flag(flag))
            return

        if args.command == "set":
            flag = _upsert_flag(
                session,
                corp_code=args.corp_code,
                enabled=args.enabled,
                reason=args.reason,
                updated_by=args.updated_by,
            )
            _refresh_cache(session)
            print(f"Set {flag.corp_code} fallback_enabled={flag.fallback_enabled}")
            return

        if args.command == "enable":
            flag = _upsert_flag(
                session,
                corp_code=args.corp_code,
                enabled=True,
                reason=args.reason,
                updated_by=args.updated_by,
            )
            _refresh_cache(session)
            print(f"Enabled viewer fallback for {flag.corp_code}")
            return

        if args.command == "disable":
            flag = _upsert_flag(
                session,
                corp_code=args.corp_code,
                enabled=False,
                reason=args.reason,
                updated_by=args.updated_by,
            )
            _refresh_cache(session)
            print(f"Disabled viewer fallback for {flag.corp_code}")
            return

        if args.command == "clear-cache":
            _refresh_cache(session)
            print("Viewer fallback flag cache refreshed.")
            return

        parser.error(f"Unknown command {args.command}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
