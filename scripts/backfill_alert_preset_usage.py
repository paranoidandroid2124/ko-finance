"""One-off utility to backfill alert preset usage analytics from existing rules."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Optional
import uuid

from sqlalchemy.orm import Session

from database import SessionLocal
from models.alert import AlertRule
from services.alerts import preset_usage_service


def _iter_preset_rules(session: Session) -> Iterable[AlertRule]:
    """Yield alert rules that contain preset metadata in their extras payload."""

    query = session.query(AlertRule).filter(AlertRule.extras.isnot(None))
    for rule in query:  # pragma: no cover - simple iteration
        extras = rule.extras or {}
        preset_id = extras.get("presetId") or extras.get("preset_id")
        if preset_id:
            yield rule


def _existing_rule_ids() -> List[str]:
    """Return rule identifiers already recorded in the usage log."""

    entries = preset_usage_service._load_entries()  # type: ignore[attr-defined]
    return [entry.rule_id for entry in entries if entry.rule_id]


def backfill(dry_run: bool = False) -> int:
    """Backfill preset usage entries for historical alert rules."""

    session = SessionLocal()
    processed = 0
    skipped = set(_existing_rule_ids())
    try:
        for rule in _iter_preset_rules(session):
            preset_id = (rule.extras or {}).get("presetId") or (rule.extras or {}).get("preset_id")
            if not preset_id:
                continue
            rule_identifier = str(rule.id)
            if rule_identifier in skipped:
                continue
            channels = []
            for entry in rule.channels or []:
                channel_type = entry.get("type")
                if channel_type:
                    channels.append(str(channel_type))
            if not channels:
                channels.append("email")
            if not dry_run:
                preset_usage_service.record_usage(
                    preset_id=str(preset_id),
                    bundle=(rule.extras or {}).get("presetBundle"),
                    plan_tier=rule.plan_tier,
                    channel_types=channels,
                    user_id=rule.user_id if isinstance(rule.user_id, uuid.UUID) else None,
                    org_id=rule.org_id if isinstance(rule.org_id, uuid.UUID) else None,
                    rule_id=rule.id if isinstance(rule.id, uuid.UUID) else None,
                )
            processed += 1
    finally:
        session.close()
    return processed


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill alert preset usage analytics.")
    parser.add_argument("--dry-run", action="store_true", help="Only report how many entries would be added.")
    args = parser.parse_args(argv)
    count = backfill(dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"Backfilled {count} preset usage entries{suffix}.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
